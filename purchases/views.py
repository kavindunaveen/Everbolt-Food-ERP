from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
import json
from decimal import Decimal
from django.http import JsonResponse
from django.db import transaction
from .models import GRN, GRNItem, PurchaseOrder, PurchaseOrderItem, POType
from suppliers.models import Supplier
from .services import confirm_grn, cancel_grn

class GRNListView(LoginRequiredMixin, ListView):
    model = GRN
    template_name = 'purchases/grn_list.html'
    context_object_name = 'grns'
    paginate_by = 20
    ordering = ['-id']

class GRNDetailView(LoginRequiredMixin, DetailView):
    model = GRN
    template_name = 'purchases/grn_detail.html'
    context_object_name = 'grn'



@login_required
def confirm_grn_view(request, pk):
    grn = get_object_or_404(GRN, pk=pk)
    if request.method == 'POST':
        try:
            confirm_grn(grn, request.user)
            messages.success(request, f"GRN {grn.grn_number} successfully confirmed. Stock updated.")
        except Exception as e:
            messages.error(request, f"Error confirming GRN: {str(e)}")
    return redirect('grn_list')

@login_required
def cancel_grn_view(request, pk):
    grn = get_object_or_404(GRN, pk=pk)
    if request.method == 'POST':
        try:
            cancel_grn(grn, request.user)
            messages.success(request, f"GRN {grn.grn_number} successfully cancelled. Stock reversed.")
        except Exception as e:
            messages.error(request, f"Error cancelling GRN: {str(e)}")
    return redirect('grn_list')

@login_required
def grn_receive_hub(request):
    # Only show CONFIRMED POs that have unreceived items
    # An item is unreceived if received_qty < qty
    confirmed_pos = PurchaseOrder.objects.filter(status=PurchaseOrder.StatusChoices.CONFIRMED)
    pos_to_show = []
    for po in confirmed_pos:
        # Check if there's remaining qty
        remaining = False
        for item in po.items.all():
            if item.received_qty < item.qty:
                remaining = True
                break
        if remaining:
            pos_to_show.append(po)

    return render(request, 'purchases/grn_hub.html', {'pos': pos_to_show})

@login_required
def grn_receive_po(request, po_id):
    po = get_object_or_404(PurchaseOrder, pk=po_id, status=PurchaseOrder.StatusChoices.CONFIRMED)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            received_items = data.get('items', [])
            if not received_items:
                return JsonResponse({'success': False, 'message': 'No items received.'})
                
            from inventory.models import Product, StockLedger
            
            with transaction.atomic():
                # Create the GRN Header
                grn = GRN.objects.create(
                    po=po,
                    supplier=po.supplier.supplier_name, # Stored as text for fallback
                    date=request.POST.get('date', data.get('date')),
                    ref_number=data.get('ref_number', ''),
                    remarks=data.get('remarks', ''),
                    status=GRN.StatusChoices.DRAFT,  # Can auto-confirm or leave as draft
                    created_by=request.user
                )

                for r_item in received_items:
                    po_item_id = r_item.get('po_item_id')
                    try:
                        po_item = PurchaseOrderItem.objects.get(id=po_item_id, po=po)
                    except PurchaseOrderItem.DoesNotExist:
                        continue
                        
                    receive_qty = Decimal(str(r_item.get('receive_qty', 0)))
                    if receive_qty <= 0:
                        continue
                        
                    if receive_qty > po_item.remaining_qty:
                        return JsonResponse({'success': False, 'message': f'Cannot receive {receive_qty} for {po_item.material_code}. Only {po_item.remaining_qty} remaining.'})
                        
                    unit_price = Decimal(str(r_item.get('unit_price', po_item.unit_price)))
                    
                    # 1. Product Synchronization Check
                    # If this material doesn't exist in the master Inventory table, silently create it.
                    prod_name = po_item.category
                    if po_item.sub_category:
                        prod_name += f" - {po_item.sub_category}"
                        
                    inv_class = Product.InventoryClasses.PACKAGING if po.po_type == POType.PACKING_MATERIAL else Product.InventoryClasses.RAW
                    
                    product, created = Product.objects.get_or_create(
                        product_id=po_item.material_code,
                        defaults={
                            'name': prod_name,
                            'inventory_class': inv_class,
                            'stock_unit': Product.UnitTypes.PCS if po_item.unit.lower() == 'pcs' else Product.UnitTypes.KG, # simplistic fallback
                            'selling_unit': Product.UnitTypes.PCS,
                            'selling_price': unit_price * Decimal('1.5'), # arbitrary placeholder
                            'custom_load_price': unit_price
                        }
                    )
                    
                    # If product already existed, we still want to update its cost price with the latest incoming price
                    if not created and product.custom_load_price != unit_price:
                        product.custom_load_price = unit_price
                        product.save(update_fields=['custom_load_price'])

                    # 2. Create GRNItem
                    # Expiry handled manually later if needed
                    GRNItem.objects.create(
                        grn=grn,
                        po_item=po_item,
                        product=product,
                        qty=receive_qty,
                        unit_cost=unit_price
                    )
                    
                    # 3. Update PO Item received count
                    po_item.received_qty += receive_qty
                    po_item.save(update_fields=['received_qty'])

                # Confirm the GRN immediately to update Stock Ledgers as requested by workflow
                from purchases.services import confirm_grn
                confirm_grn(grn, request.user)

            return JsonResponse({'success': True, 'redirect_url': reverse('grn_list')})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
            
    # GET Logic
    items_to_receive = []
    for item in po.items.all():
        if item.remaining_qty > 0:
            items_to_receive.append({
                'id': item.id,
                'category': item.category,
                'sub_category': item.sub_category,
                'material_code': item.material_code,
                'unit': item.unit,
                'remaining_qty': float(item.remaining_qty),
                'unit_price': float(item.unit_price)
            })
            
    context = {
        'po': po,
        'items_json': json.dumps(items_to_receive)
    }
    return render(request, 'purchases/grn_receive_form.html', context)


@login_required
def purchase_order_hub(request):
    # This is the new entry point for purchases module
    return render(request, 'purchases/po_hub.html')

class PurchaseOrderListView(LoginRequiredMixin, ListView):
    model = PurchaseOrder
    template_name = 'purchases/po_list.html'
    context_object_name = 'pos'
    paginate_by = 20
    ordering = ['-id']

@login_required
def purchase_order_create(request, po_type):
    if po_type not in ['raw', 'packing']:
        return redirect('po_hub')
        
    actual_type = POType.RAW_MATERIAL if po_type == 'raw' else POType.PACKING_MATERIAL
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            supplier_id = data.get('supplier_id')
            date = data.get('date')
            attention = data.get('attention', '')
            payment_term = data.get('payment_term', 'CREDIT')
            apply_vat = data.get('apply_vat', False)
            items = data.get('items', [])
            
            if not supplier_id or not date or not items:
                return JsonResponse({'success': False, 'message': 'Missing required fields (Supplier, Date, or Items).'})
                
            supplier = Supplier.objects.get(id=supplier_id)
            
            with transaction.atomic():
                po = PurchaseOrder.objects.create(
                    po_type=actual_type,
                    supplier=supplier,
                    date=date,
                    attention=attention,
                    payment_term=payment_term,
                    apply_vat=apply_vat,
                    created_by=request.user
                )
                
                for item in items:
                    PurchaseOrderItem.objects.create(
                        po=po,
                        category=item.get('category'),
                        sub_category=item.get('sub_category'),
                        material_code=item.get('material_code', ''),
                        unit=item.get('unit'),
                        qty=item.get('qty'),
                        unit_price=item.get('unit_price', 0.00)
                    )
            
            # Send back redirect URL so JS can redirect
            return JsonResponse({'success': True, 'redirect_url': reverse('po_detail', args=[po.id])})
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})

    suppliers = Supplier.objects.all()
    # To properly initialize generating sequences, pass the next sequence placeholder to form visually
    # EFPO format check
    last_po = PurchaseOrder.objects.filter(po_number__startswith="EFPO-").order_by('-po_number').first()
    if last_po:
        try:
            next_seq = int(last_po.po_number.split('-')[1]) + 1
        except:
            next_seq = 1
    else:
        next_seq = 1
    preview_po_number = f"EFPO-{next_seq:04d}"

    return render(request, 'purchases/po_form.html', {
        'po_type': actual_type,
        'po_type_str': po_type,
        'suppliers': suppliers,
        'preview_po_number': preview_po_number
    })

class PurchaseOrderDetailView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchases/po_detail.html'
    context_object_name = 'po'

class PurchaseOrderPrintView(LoginRequiredMixin, DetailView):
    model = PurchaseOrder
    template_name = 'purchases/po_print.html'
    context_object_name = 'po'

@login_required
def purchase_order_confirm(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status == PurchaseOrder.StatusChoices.DRAFT:
        po.status = PurchaseOrder.StatusChoices.CONFIRMED
        po.save()
        messages.success(request, f"Purchase Order {po.po_number} Confirmed successfully.")
    else:
        messages.warning(request, "Only DRAFT orders can be confirmed.")
    return redirect('po_detail', pk=pk)

@login_required
def purchase_order_cancel(request, pk):
    po = get_object_or_404(PurchaseOrder, pk=pk)
    if po.status in [PurchaseOrder.StatusChoices.DRAFT, PurchaseOrder.StatusChoices.CONFIRMED]:
        # Check if already fulfilled partially
        received_items = po.items.filter(received_qty__gt=0)
        if received_items.exists() and po.status == PurchaseOrder.StatusChoices.CONFIRMED:
            messages.warning(request, "Cannot cancel a PO that has already been partially received via GRN.")
        else:
            po.status = PurchaseOrder.StatusChoices.CANCELLED
            po.save()
            messages.success(request, f"Purchase Order {po.po_number} has been Cancelled.")
    return redirect('po_detail', pk=pk)

