from django.shortcuts import render, get_object_or_404
from django.urls import reverse_lazy
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from users.mixins import ERPPermissionRequiredMixin
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.views import View
from sales.views import AdminRequiredMixin
from .models import Customer, CustomerChangeLog, CustomerDeliveryAddress
from .forms import CustomerForm

class CustomerListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = Customer
    template_name = 'crm/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20
    permission_required = 'crm.view_customer'

    def get_queryset(self):
        qs = super().get_queryset()
        
        has_sales = self.request.GET.get('has_sales')
        if has_sales == 'true':
            qs = qs.filter(invoice__isnull=False).distinct()
        elif has_sales == 'false':
            qs = qs.filter(invoice__isnull=True)
            
        customer_type = self.request.GET.get('customer_type')
        if customer_type:
            qs = qs.filter(customer_type=customer_type)
            
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(customer_name__icontains=q) | qs.filter(customer_code__icontains=q) | qs.filter(company_name__icontains=q)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Customer')
        except ImportError:
            context['saved_filters'] = []
        context['model_name'] = 'Customer'
        return context

class CustomerCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'crm.add_customer'

    def form_valid(self, form):
        response = super().form_valid(form)
        CustomerChangeLog.objects.create(
            customer=self.object,
            changed_by=self.request.user,
            details="Customer created."
        )
        return response

class CustomerUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'crm.change_customer'

    def form_valid(self, form):
        if form.has_changed():
            changed_fields = []
            from django.forms.models import ModelChoiceField
            for field in form.changed_data:
                old_val = form.initial.get(field, 'None')
                new_val = form.cleaned_data.get(field, 'None')
                
                if isinstance(form.fields[field], ModelChoiceField):
                    if old_val and old_val != 'None':
                        old_obj = form.fields[field].queryset.filter(pk=old_val).first()
                        if old_obj:
                            old_val = str(old_obj)
                            
                changed_fields.append(f"{field.replace('_', ' ').capitalize()} changed from '{old_val}' to '{new_val}'")
            CustomerChangeLog.objects.create(
                customer=self.object,
                changed_by=self.request.user,
                details=" | ".join(changed_fields)
            )
        return super().form_valid(form)

class CustomerDeleteView(LoginRequiredMixin, ERPPermissionRequiredMixin, DeleteView):
    model = Customer
    template_name = 'crm/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'crm.delete_customer'

class CustomerDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    model = Customer
    template_name = 'crm/customer_detail.html'
    context_object_name = 'customer'
    permission_required = 'crm.view_customer'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        customer = self.object
        invoices = customer.invoice_set.all()
        
        # Outstanding Balance
        unpaid_invoices = invoices.exclude(status='PAID').exclude(status='CANCELLED')
        context['outstanding_balance'] = unpaid_invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Purchase history
        context['purchase_history'] = invoices.exclude(status='CANCELLED').order_by('-creation_date').prefetch_related('items__product')
        
        # Metrics for Smart Buttons
        context['invoice_count'] = invoices.count()
        context['total_invoiced'] = invoices.exclude(status='CANCELLED').aggregate(Sum('total_amount'))['total_amount__sum'] or 0
        
        # Audit Logs
        context['change_logs'] = customer.change_logs.all()[:50]
        
        # Monthly Chart Data (Trailing 6 months)
        from datetime import datetime, timedelta
        from django.db.models.functions import TruncMonth
        from django.utils import timezone

        six_months_ago = timezone.now() - timedelta(days=180)
        monthly_sales = invoices.filter(creation_date__gte=six_months_ago, status__in=['ISSUED', 'PAID'])\
            .annotate(month=TruncMonth('creation_date'))\
            .values('month')\
            .annotate(total=Sum('total_amount'))\
            .order_by('month')
            
        labels = []
        data = []
        for entry in monthly_sales:
            if entry['month']:
                labels.append(entry['month'].strftime('%b %Y'))
                data.append(float(entry['total']))
                
        context['chart_labels'] = labels
        context['chart_data'] = data
        
        return context

import csv
from django.http import HttpResponse
from django.views.generic import View

class CustomerExportView(LoginRequiredMixin, ERPPermissionRequiredMixin, View):
    permission_required = 'crm.view_customer'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="customers.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'Customer Code', 'Customer Name', 'Company Name', 'Contact Person', 
            'Phone', 'Email', 'Customer Type', 'Payment Terms', 'Credit Limit', 
            'Assigned Sales Officer', 'VAT Enabled', 'Registration Date'
        ])
        
        qs = Customer.objects.all().order_by('-registration_date')
        
        has_sales = request.GET.get('has_sales')
        if has_sales == 'true':
            qs = qs.filter(invoice__isnull=False).distinct()
        elif has_sales == 'false':
            qs = qs.filter(invoice__isnull=True)
            
        customer_type = request.GET.get('customer_type')
        if customer_type:
            qs = qs.filter(customer_type=customer_type)
            
        q = request.GET.get('q')
        if q:
            qs = qs.filter(customer_name__icontains=q) | qs.filter(customer_code__icontains=q) | qs.filter(company_name__icontains=q)
            
        for c in qs:
            writer.writerow([
                c.customer_code,
                c.customer_name,
                c.company_name or 'N/A',
                c.contact_person,
                c.phone,
                c.email or 'N/A',
                c.get_customer_type_display(),
                c.get_payment_terms_display(),
                c.credit_limit,
                c.assigned_sales_officer.get_full_name() if c.assigned_sales_officer else 'N/A',
                'Yes' if c.vat_enabled else 'No',
                c.registration_date
            ])
            
        return response


# ─── Delivery Address AJAX views ─────────────────────────────────────────────

def _serialize_addr(a):
    return {
        'id':         a.pk,
        'label':      a.label,
        'line1':      a.line1 or '',
        'line2':      a.line2 or '',
        'city':       a.city  or '',
        'province':   a.province or '',
        'zip_code':   a.zip_code or '',
        'is_default': a.is_default,
        'formatted':  a.formatted,
    }


@login_required
def customer_delivery_addresses(request, pk):
    """GET: return all delivery addresses for a customer (used by invoice form AJAX)."""
    customer = get_object_or_404(Customer, pk=pk)
    addrs = list(customer.delivery_addresses.all())

    # Fallback: if no saved addresses yet, synthesise one from the old single fields
    if not addrs and (customer.delivery_address_line1 or customer.delivery_city):
        fallback = CustomerDeliveryAddress(
            customer=customer,
            label='Default',
            line1=customer.delivery_address_line1 or '',
            line2=customer.delivery_address_line2 or '',
            city=customer.delivery_city or '',
            province=customer.delivery_province or '',
            zip_code=customer.delivery_zip_code or '',
            is_default=True,
        )
        return JsonResponse({'addresses': [_serialize_addr(fallback)]})

    return JsonResponse({'addresses': [_serialize_addr(a) for a in addrs]})


@login_required
@require_POST
def add_delivery_address(request, pk):
    """POST: add a new delivery address to a customer."""
    customer = get_object_or_404(Customer, pk=pk)
    label    = request.POST.get('label', '').strip()
    if not label:
        return JsonResponse({'error': 'Label is required.'}, status=400)

    is_default = request.POST.get('is_default') == 'true'
    # If this is the first address, auto-make it default
    if not customer.delivery_addresses.exists():
        is_default = True

    addr = CustomerDeliveryAddress.objects.create(
        customer   = customer,
        label      = label,
        line1      = request.POST.get('line1', '').strip() or None,
        line2      = request.POST.get('line2', '').strip() or None,
        city       = request.POST.get('city', '').strip()  or None,
        province   = request.POST.get('province', '').strip() or None,
        zip_code   = request.POST.get('zip_code', '').strip() or None,
        is_default = is_default,
    )
    CustomerChangeLog.objects.create(
        customer=customer,
        changed_by=request.user,
        details=f"Added delivery address: {addr.label}"
    )
    return JsonResponse({'address': _serialize_addr(addr)})


@login_required
@require_POST
def set_default_delivery_address(request, pk, addr_pk):
    """POST: mark an address as the default for a customer."""
    customer = get_object_or_404(Customer, pk=pk)
    addr     = get_object_or_404(CustomerDeliveryAddress, pk=addr_pk, customer=customer)
    addr.is_default = True
    addr.save()  # model.save() clears other defaults automatically
    CustomerChangeLog.objects.create(
        customer=customer,
        changed_by=request.user,
        details=f"Set default delivery address to: {addr.label}"
    )
    return JsonResponse({'ok': True, 'addresses': [_serialize_addr(a) for a in customer.delivery_addresses.all()]})


@login_required
@require_POST
def delete_delivery_address(request, pk, addr_pk):
    """POST: delete a delivery address."""
    customer = get_object_or_404(Customer, pk=pk)
    addr     = get_object_or_404(CustomerDeliveryAddress, pk=addr_pk, customer=customer)
    label    = addr.label
    was_default = addr.is_default
    addr.delete()
    # If we deleted the default, promote the first remaining address
    if was_default:
        first = customer.delivery_addresses.first()
        if first:
            first.is_default = True
            first.save()
    CustomerChangeLog.objects.create(
        customer=customer,
        changed_by=request.user,
        details=f"Deleted delivery address: {label}"
    )
    return JsonResponse({'ok': True, 'addresses': [_serialize_addr(a) for a in customer.delivery_addresses.all()]})

