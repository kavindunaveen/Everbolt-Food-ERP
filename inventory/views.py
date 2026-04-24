from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Q
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
import csv
import io
from decimal import Decimal
from .models import Product, StockAdjustment, StockLedger
from .forms import ProductForm, StockAdjustmentForm
from .services import confirm_stock_adjustment, cancel_stock_adjustment

class ProductDetailAPIView(LoginRequiredMixin, View):
    def get(self, request, pk, *args, **kwargs):
        try:
            product = Product.objects.get(pk=pk)
            return JsonResponse({
                'id': product.id,
                'selling_price': str(product.selling_price),
                'price_tier_100': str(product.price_tier_100) if product.price_tier_100 else None,
                'price_tier_250': str(product.price_tier_250) if product.price_tier_250 else None,
                'price_tier_500': str(product.price_tier_500) if product.price_tier_500 else None,
                'current_stock': str(product.current_stock)
            })
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    paginate_by = 20
    permission_required = 'inventory.view_product'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        category = self.request.GET.get('category')
        
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(product_id__icontains=q))
        
        if category:
            qs = qs.filter(category=category)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Product.CategoryChoices.choices
        context['model_name'] = 'Product'
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Product')
        except ImportError:
            context['saved_filters'] = []
        return context

class ProductCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product_list')
    permission_required = 'inventory.add_product'

class ProductUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Product
    form_class = ProductForm
    template_name = 'inventory/product_form.html'
    success_url = reverse_lazy('product_list')
    permission_required = 'inventory.change_product'

class ProductDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Product
    template_name = 'inventory/product_confirm_delete.html'
    success_url = reverse_lazy('product_list')
    permission_required = 'inventory.delete_product'

@login_required
def bulk_export_products(request):
    if request.method == 'POST':
        product_ids = request.POST.getlist('selected_products')
        products = Product.objects.filter(id__in=product_ids)
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="products_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'System ID', 'Product ID', 'Name', 
            'Category', 'Brand', 'Tea Type', 'Packet Size', 'Stock Unit', 'Selling Unit',
            'Inventory Class', 'Production Type',
            'Selling Price', 'Custom Load Price',
            'Reorder Level', 'Track Stock', 'Allow Negative Stock', 'Tax Rate', 'Status',
            'Current Stock'
        ])
        
        for p in products:
            writer.writerow([
                p.id, p.product_id, p.name,
                p.category,
                p.brand,
                p.tea_type or '',
                p.packet_size or '', p.stock_unit, p.selling_unit,
                p.inventory_class, p.product_type,
                p.selling_price, p.custom_load_price or '',
                p.reorder_level, p.track_stock, p.allow_negative_stock, p.tax_rate, p.status,
                p.current_stock
            ])
            
        return response
    return redirect('product_list')

@login_required
def bulk_delete_products(request):
    if request.method == 'POST':
        product_ids = request.POST.getlist('selected_products')
        count, _ = Product.objects.filter(id__in=product_ids).delete()
        if count > 0:
            messages.success(request, f"Successfully deleted {count} products.")
    return redirect('product_list')

class ProductImportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'inventory.add_product'

    def get(self, request):
        return render(request, 'inventory/product_import.html')

    def post(self, request):
        if 'import_file' not in request.FILES:
            messages.error(request, 'Please upload a valid CSV file.')
            return redirect('product_import')
            
        csv_file = request.FILES['import_file']
        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'File must be a CSV file.')
            return redirect('product_import')

        try:
            # Decode file
            dataset = csv_file.read().decode('utf-8-sig').splitlines()
            reader = csv.DictReader(dataset)
            
            created_count = 0
            updated_count = 0
            
            for row in reader:
                sys_id = row.get('System ID')
                prod_id = row.get('Product ID')
                name = row.get('Name')
                
                if not name:
                    continue
                    
                cat_name = row.get('Category')
                brand_name = row.get('Brand')
                tea_type = row.get('Tea Type')
                packet_size = row.get('Packet Size')
                stock_unit = row.get('Stock Unit')
                selling_unit = row.get('Selling Unit')
                inv_class = row.get('Inventory Class')
                prod_type = row.get('Production Type')
                
                selling_price = row.get('Selling Price')
                custom_price = row.get('Custom Load Price')
                reorder_lvl = row.get('Reorder Level')
                tax_rate = row.get('Tax Rate')
                
                def parse_bool(val, default):
                    if val is None or val == '':
                        return default
                    return str(val).lower() in ['true', '1', 'yes', 'y']
                
                track_stock = parse_bool(row.get('Track Stock'), True)
                allow_neg = parse_bool(row.get('Allow Negative Stock'), False)
                status = parse_bool(row.get('Status'), True)
                
                defaults = {
                    'name': name,
                    'category': cat_name.strip() if cat_name else 'Confectionery',
                    'brand': brand_name.strip() if brand_name else 'Everbolt',
                    'tea_type': tea_type.strip() if tea_type else None,
                    'packet_size': packet_size if packet_size else None,
                    'selling_price': Decimal(selling_price.replace(',', '')) if selling_price else Decimal('0.00'),
                    'custom_load_price': Decimal(custom_price.replace(',', '')) if custom_price else None,
                    'reorder_level': Decimal(reorder_lvl.replace(',', '')) if reorder_lvl else Decimal('0.000'),
                    'tax_rate': Decimal(tax_rate.replace(',', '')) if tax_rate else Decimal('18.00'),
                    'track_stock': track_stock,
                    'allow_negative_stock': allow_neg,
                    'status': status,
                }
                
                if stock_unit: defaults['stock_unit'] = stock_unit
                if selling_unit: defaults['selling_unit'] = selling_unit
                if inv_class: defaults['inventory_class'] = inv_class
                if prod_type: defaults['product_type'] = prod_type
                
                if prod_id: defaults['product_id'] = prod_id
                
                product = None
                is_new = False
                
                if sys_id and sys_id.strip():
                    product = Product.objects.filter(id=sys_id).first()
                if not product and prod_id:
                    product = Product.objects.filter(product_id=prod_id).first()
                    
                if product:
                    for k, v in defaults.items():
                        setattr(product, k, v)
                    product.save()
                    updated_count += 1
                else:
                    product = Product.objects.create(**defaults)
                    created_count += 1
                    is_new = True
                
                # Handle Stock Field
                current_stock_val = row.get('Current Stock')
                if current_stock_val and current_stock_val.strip() and product.track_stock:
                    try:
                        qty = Decimal(current_stock_val.replace(',', ''))
                        if product.current_stock != qty:
                            diff = qty - product.current_stock
                            tx_type = StockLedger.TransactionTypes.OPENING if (is_new or product.current_stock == 0) else (StockLedger.TransactionTypes.ADJ_POS if diff > 0 else StockLedger.TransactionTypes.ADJ_NEG)
                            qty_in = diff if diff > 0 else Decimal('0.0')
                            qty_out = -diff if diff < 0 else Decimal('0.0')
                            
                            StockLedger.objects.create(
                                product=product,
                                tx_type=tx_type,
                                qty_in=qty_in,
                                qty_out=qty_out,
                                reference_type='SYS-IMPORT',
                                reference_number='IMPORT',
                                remarks='Import stock update',
                                user=request.user
                            )
                            # Update Cache
                            product.current_stock = qty
                            product.save(update_fields=['current_stock'])
                    except Exception as ex:
                        pass # Ignore invalid stock values
                        
            messages.success(request, f"Import successful: {created_count} created, {updated_count} updated.")
            return redirect('product_list')
        except Exception as e:
            messages.error(request, f"Error processing file: {str(e)}")
            return redirect('product_import')

@login_required
def download_import_template(request):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="product_import_template.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'System ID', 'Product ID', 'Name', 
        'Category', 'Brand', 'Tea Type', 'Packet Size', 'Stock Unit', 'Selling Unit',
        'Inventory Class', 'Production Type',
        'Selling Price', 'Custom Load Price',
        'Reorder Level', 'Track Stock', 'Allow Negative Stock', 'Tax Rate', 'Status',
        'Current Stock'
    ])
    # Give an example row to help the user understand
    writer.writerow([
        '', '', 'Sample Product Name', 
        'Tea', 'Everbolt', 'Herbal Tea', '500g', 'pcs', 'pcs',
        'FINISHED', 'MANUFACTURED',
        '1500.00', '', 
        '10.00', 'TRUE', 'FALSE', '18.00', 'TRUE',
        '100'
    ])
    return response

# Stock Adjustment Views
class StockAdjustmentListView(LoginRequiredMixin, ListView):
    model = StockAdjustment
    template_name = 'inventory/adjustment_list.html'
    context_object_name = 'adjustments'
    paginate_by = 20
    ordering = ['-id']

class StockAdjustmentCreateView(LoginRequiredMixin, CreateView):
    model = StockAdjustment
    form_class = StockAdjustmentForm
    template_name = 'inventory/adjustment_form.html'
    success_url = reverse_lazy('adjustment_list')

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, "Stock Adjustment created as Draft.")
        return super().form_valid(form)

class StockAdjustmentDetailView(LoginRequiredMixin, DetailView):
    model = StockAdjustment
    template_name = 'inventory/adjustment_detail.html'
    context_object_name = 'adjustment'

@login_required
def confirm_adjustment_view(request, pk):
    adjustment = get_object_or_404(StockAdjustment, pk=pk)
    if request.method == 'POST':
        try:
            confirm_stock_adjustment(adjustment, request.user)
            messages.success(request, f"Adjustment {adjustment.adjustment_number} confirmed. Stock updated.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('adjustment_list')

@login_required
def cancel_adjustment_view(request, pk):
    adjustment = get_object_or_404(StockAdjustment, pk=pk)
    if request.method == 'POST':
        try:
            cancel_stock_adjustment(adjustment, request.user)
            messages.success(request, f"Adjustment {adjustment.adjustment_number} cancelled. Stock reversed.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('adjustment_list')

# Inventory Reports/Views
class StockSummaryView(LoginRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/stock_summary.html'
    context_object_name = 'products'
    paginate_by = 20

    def get_queryset(self):
        return Product.objects.filter(track_stock=True, status=True)

class StockLedgerView(LoginRequiredMixin, ListView):
    model = StockLedger
    template_name = 'inventory/stock_ledger.html'
    context_object_name = 'entries'
    paginate_by = 20
    ordering = ['-date']

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.GET.get('product')
        if query:
            qs = qs.filter(
                Q(product__product_id__icontains=query) | 
                Q(product__name__icontains=query)
            )
        return qs
