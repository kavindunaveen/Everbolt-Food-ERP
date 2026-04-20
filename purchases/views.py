from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from .models import GRN
from .forms import GRNForm, GRNItemFormSet
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

class GRNCreateView(LoginRequiredMixin, CreateView):
    model = GRN
    form_class = GRNForm
    template_name = 'purchases/grn_form.html'
    success_url = reverse_lazy('grn_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = GRNItemFormSet(self.request.POST)
        else:
            data['items'] = GRNItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            form.instance.created_by = self.request.user
            self.object = form.save()
            items.instance = self.object
            items.save()
            messages.success(self.request, f"GRN {self.object.grn_number} created successfully as Draft.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class GRNUpdateView(LoginRequiredMixin, UpdateView):
    model = GRN
    form_class = GRNForm
    template_name = 'purchases/grn_form.html'
    success_url = reverse_lazy('grn_list')

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().status != GRN.StatusChoices.DRAFT:
            messages.error(request, "Only Draft GRNs can be edited.")
            return redirect('grn_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = GRNItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = GRNItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            self.object = form.save()
            items.instance = self.object
            items.save()
            messages.success(self.request, f"GRN {self.object.grn_number} updated.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

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

import json
from django.http import JsonResponse
from django.db import transaction
from .models import PurchaseOrder, PurchaseOrderItem, POType
from suppliers.models import Supplier

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

