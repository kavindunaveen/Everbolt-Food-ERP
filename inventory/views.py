from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from sales.views import AdminRequiredMixin
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
                'current_stock': str(product.current_stock)
            })
        except Product.DoesNotExist:
            return JsonResponse({'error': 'Product not found'}, status=404)

class ProductListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Product
    template_name = 'inventory/product_list.html'
    context_object_name = 'products'
    permission_required = 'inventory.view_product'

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(name__icontains=q) | qs.filter(sku__icontains=q) | qs.filter(product_id__icontains=q)
        return qs

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

# Stock Adjustment Views
class StockAdjustmentListView(LoginRequiredMixin, ListView):
    model = StockAdjustment
    template_name = 'inventory/adjustment_list.html'
    context_object_name = 'adjustments'
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

    def get_queryset(self):
        return Product.objects.filter(track_stock=True, status=True)

class StockLedgerView(LoginRequiredMixin, ListView):
    model = StockLedger
    template_name = 'inventory/stock_ledger.html'
    context_object_name = 'entries'
    ordering = ['-date']

    def get_queryset(self):
        qs = super().get_queryset()
        product_id = self.request.GET.get('product')
        if product_id:
            qs = qs.filter(product_id=product_id)
        return qs
