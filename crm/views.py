from django.shortcuts import render
from django.urls import reverse_lazy
from django.db.models import Sum
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from sales.views import AdminRequiredMixin
from .models import Customer, CustomerChangeLog
from .forms import CustomerForm

class CustomerListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
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

class CustomerCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
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

class CustomerUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'crm/customer_form.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'crm.change_customer'

    def form_valid(self, form):
        if form.has_changed():
            changed_fields = []
            for field in form.changed_data:
                old_val = form.initial.get(field, 'None')
                new_val = form.cleaned_data.get(field, 'None')
                changed_fields.append(f"{field.replace('_', ' ').capitalize()} changed from '{old_val}' to '{new_val}'")
            CustomerChangeLog.objects.create(
                customer=self.object,
                changed_by=self.request.user,
                details=" | ".join(changed_fields)
            )
        return super().form_valid(form)

class CustomerDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    model = Customer
    template_name = 'crm/customer_confirm_delete.html'
    success_url = reverse_lazy('customer_list')
    permission_required = 'crm.delete_customer'

class CustomerDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
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

