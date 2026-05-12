from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.contrib import messages
from django.db.models import Q
from .models import Supplier, SupplierType, ProvinceChoices
from .forms import SupplierForm

class SupplierListView(LoginRequiredMixin, ListView):
    model = Supplier
    template_name = 'suppliers/supplier_list.html'
    context_object_name = 'suppliers'
    paginate_by = 20
    ordering = ['-created_at']

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(supplier_code__icontains=q) |
                Q(supplier_name__icontains=q) |
                Q(contact_number__icontains=q)
            )
            
        # Optional: Add advanced filtering by supplier_type
        supplier_type = self.request.GET.get('supplier_type')
        if supplier_type:
            qs = qs.filter(supplier_type=supplier_type)
            
        province = self.request.GET.get('province')
        if province:
            qs = qs.filter(province=province)
            
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # For the new filter_bar.html component
        context['model_name'] = 'Supplier'
        context['supplier_types'] = SupplierType.choices
        context['provinces'] = ProvinceChoices.choices
        if hasattr(self.request.user, 'saved_filters'):
            context['saved_filters'] = self.request.user.saved_filters.filter(model_name='Supplier')
        return context

class SupplierDetailView(LoginRequiredMixin, DetailView):
    model = Supplier
    template_name = 'suppliers/supplier_detail.html'
    context_object_name = 'supplier'

class SupplierCreateView(LoginRequiredMixin, CreateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'
    success_url = reverse_lazy('supplier_list')

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.supplier_name}' successfully created.")
        return super().form_valid(form)

class SupplierUpdateView(LoginRequiredMixin, UpdateView):
    model = Supplier
    form_class = SupplierForm
    template_name = 'suppliers/supplier_form.html'

    def get_success_url(self):
        return reverse_lazy('supplier_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        messages.success(self.request, f"Supplier '{form.instance.supplier_name}' successfully updated.")
        return super().form_valid(form)

class SupplierDeleteView(LoginRequiredMixin, DeleteView):
    model = Supplier
    template_name = 'suppliers/supplier_confirm_delete.html'
    success_url = reverse_lazy('supplier_list')

    def delete(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(self.request, f"Supplier '{obj.supplier_name}' successfully deleted.")
        return super().delete(request, *args, **kwargs)

import csv
from django.http import HttpResponse
from django.views.generic import View

class SupplierExportView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="suppliers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Supplier Code', 'Supplier Name', 'Supplier Type', 'Email', 
            'Contact Number', 'Alternate Contact Number', 'Address Line 1', 
            'Address Line 2', 'City', 'Province', 'Zip Code', 
            'Bank Name', 'Bank Branch', 'Bank Account No', 'VAT Reg Num'
        ])
        
        qs = Supplier.objects.all().order_by('-created_at')
        
        q = request.GET.get('q', '')
        if q:
            qs = qs.filter(
                Q(supplier_code__icontains=q) |
                Q(supplier_name__icontains=q) |
                Q(contact_number__icontains=q)
            )
            
        supplier_type = request.GET.get('supplier_type')
        if supplier_type:
            qs = qs.filter(supplier_type=supplier_type)
            
        province = request.GET.get('province')
        if province:
            qs = qs.filter(province=province)
            
        for s in qs:
            writer.writerow([
                s.supplier_code,
                s.supplier_name,
                s.get_supplier_type_display(),
                s.email or 'N/A',
                s.contact_number,
                s.alternate_contact_number or 'N/A',
                s.address_line1,
                s.address_line2 or '',
                s.city,
                s.get_province_display(),
                s.zip_code or '',
                s.get_bank_name_display() if s.bank_name else '',
                s.bank_branch or '',
                s.bank_account_no or '',
                s.vat_reg_num or ''
            ])
            
        return response
