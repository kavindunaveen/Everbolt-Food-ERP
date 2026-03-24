from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse

from .models import BOM, BOMItem, Production
from inventory.models import Product
from .forms import (
    BOMForm, BOMItemFormSet, 
    ProductionForm, ProductionMaterialFormSet, ProductionOutputFormSet
)
from .services import confirm_production, cancel_production

# --- BOM Views ---

class BOMListView(LoginRequiredMixin, ListView):
    model = BOM
    template_name = 'manufacturing/bom_list.html'
    context_object_name = 'boms'
    paginate_by = 20
    ordering = ['-id']

class BOMCreateView(LoginRequiredMixin, CreateView):
    model = BOM
    form_class = BOMForm
    template_name = 'manufacturing/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = BOMItemFormSet(self.request.POST)
        else:
            data['items'] = BOMItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
        return super().form_valid(form)

class BOMDetailView(LoginRequiredMixin, DetailView):
    model = BOM
    template_name = 'manufacturing/bom_detail.html'
    context_object_name = 'bom'

class BOMUpdateView(LoginRequiredMixin, UpdateView):
    model = BOM
    form_class = BOMForm
    template_name = 'manufacturing/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = BOMItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = BOMItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
        return super().form_valid(form)

# --- Production Views ---

class ProductionListView(LoginRequiredMixin, ListView):
    model = Production
    template_name = 'manufacturing/production_list.html'
    context_object_name = 'productions'
    paginate_by = 20
    ordering = ['-id']

class ProductionCreateView(LoginRequiredMixin, CreateView):
    model = Production
    form_class = ProductionForm
    template_name = 'manufacturing/production_form.html'
    success_url = reverse_lazy('production_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['materials'] = ProductionMaterialFormSet(self.request.POST, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(self.request.POST, prefix='outputs')
        else:
            data['materials'] = ProductionMaterialFormSet(prefix='materials')
            data['outputs'] = ProductionOutputFormSet(prefix='outputs')
        data['all_products'] = Product.objects.all()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        materials = context['materials']
        outputs = context['outputs']
        
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
            
            if materials.is_valid() and outputs.is_valid():
                materials.instance = self.object
                materials.save()
                outputs.instance = self.object
                outputs.save()
            else:
                # If formsets are invalid, return form_invalid
                return self.form_invalid(form)
                
        messages.success(self.request, "Production order created as Draft.")
        return super().form_valid(form)

class ProductionUpdateView(LoginRequiredMixin, UpdateView):
    model = Production
    form_class = ProductionForm
    template_name = 'manufacturing/production_form.html'
    success_url = reverse_lazy('production_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['materials'] = ProductionMaterialFormSet(self.request.POST, instance=self.object, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(self.request.POST, instance=self.object, prefix='outputs')
        else:
            data['materials'] = ProductionMaterialFormSet(instance=self.object, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(instance=self.object, prefix='outputs')
        data['all_products'] = Product.objects.all()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        materials = context['materials']
        outputs = context['outputs']
        with transaction.atomic():
            self.object = form.save()
            if materials.is_valid() and outputs.is_valid():
                materials.instance = self.object
                materials.save()
                outputs.instance = self.object
                outputs.save()
        return super().form_valid(form)

class ProductionDetailView(LoginRequiredMixin, DetailView):
    model = Production
    template_name = 'manufacturing/production_detail.html'
    context_object_name = 'production'

@login_required
def confirm_production_view(request, pk):
    production = get_object_or_404(Production, pk=pk)
    if request.method == 'POST':
        try:
            confirm_production(production, request.user)
            messages.success(request, f"Production {production.production_number} confirmed. Stock adjusted.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('production_detail', pk=pk)

@login_required
def cancel_production_view(request, pk):
    production = get_object_or_404(Production, pk=pk)
    if request.method == 'POST':
        try:
            cancel_production(production, request.user)
            messages.success(request, f"Production {production.production_number} cancelled. Stock reversed.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('production_detail', pk=pk)

# AJAX API to get BOM details
def get_bom_details(request, bom_id):
    bom = get_object_or_404(BOM, pk=bom_id)
    items = []
    for item in bom.items.all():
        items.append({
            'product_id': item.component_product.id,
            'product_name': item.component_product.name,
            'qty': str(item.qty_required)
        })
    return JsonResponse({
        'finished_product_id': bom.finished_product.id,
        'finished_product_name': bom.finished_product.name,
        'items': items
    })
