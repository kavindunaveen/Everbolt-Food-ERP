from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View, DetailView
from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.urls import reverse_lazy
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal
from .models import Quotation, Invoice
from .forms import QuotationForm, QuotationItemFormSet, InvoiceForm, InvoiceItemFormSet
from .services import issue_invoice, cancel_invoice, send_invoice_approval_email
import csv
from num2words import num2words

def get_next_invoice_number():
    prefix = timezone.now().strftime('%y%b').upper() + "_EBFR_"
    existing = Invoice.objects.filter(invoice_number__startswith=prefix).values_list('invoice_number', flat=True)
    used = []
    for num in existing:
        try:
            used.append(int(num.split('_')[-1]))
        except ValueError:
            pass
    next_num = 1
    while next_num in used:
        next_num += 1
    return f"{prefix}{next_num:05d}"
    
def get_next_quotation_number():
    prefix = timezone.now().strftime('%y%b').upper() + "_EBFR_QUO_"
    existing = Quotation.objects.filter(quotation_number__startswith=prefix).values_list('quotation_number', flat=True)
    used = []
    for num in existing:
        try:
            used.append(int(num.split('_')[-1]))
        except ValueError:
            pass
    next_num = 1
    while next_num in used:
        next_num += 1
    return f"{prefix}{next_num:05d}"

class AdminRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin()

class MainDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/main_dashboard.html'

class SalesDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Limit strictly to the logged-in officer's records
        q = self.request.GET.get('q')
        
        if not self.request.user.has_perm('sales.approve_invoice'):
            quotations = Quotation.objects.filter(salesperson=self.request.user).order_by('-creation_date')
            invoices = Invoice.objects.filter(salesperson=self.request.user).order_by('-creation_date')
        else:
            quotations = Quotation.objects.all().order_by('-creation_date')
            invoices = Invoice.objects.all().order_by('-creation_date')
        
        if q:
            quotations = quotations.filter(quotation_number__icontains=q)
            invoices = invoices.filter(invoice_number__icontains=q)
            
        context['recent_quotations'] = quotations[:15]
        context['recent_invoices'] = invoices[:15]
        
        context['total_invoice_amount'] = invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        return context

class QuotationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Quotation
    template_name = 'sales/quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20
    permission_required = 'sales.view_quotation'
    
    def get_queryset(self):
        qs = super().get_queryset().order_by('-creation_date')
        if not self.request.user.has_perm('sales.approve_invoice'):
            qs = qs.filter(salesperson=self.request.user)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(quotation_number__icontains=q)
        return qs

class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Invoice
    template_name = 'sales/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    permission_required = 'sales.view_invoice'
    
    def get_queryset(self):
        qs = super().get_queryset().order_by('-creation_date')
        if not self.request.user.has_perm('sales.approve_invoice'):
            qs = qs.filter(salesperson=self.request.user)
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(invoice_number__icontains=q)
        return qs

class QuotationCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'sales/quotation_form.html'
    success_url = reverse_lazy('quotation_list')
    permission_required = 'sales.add_quotation'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = QuotationItemFormSet(self.request.POST)
        else:
            data['items'] = QuotationItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.salesperson = self.request.user
            # Generate sequential gap-filling number
            self.object.quotation_number = get_next_quotation_number()
            
            if items.is_valid():
                self.object.save()
                items.instance = self.object
                
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                for item in saved_items:
                    item.quotation = self.object
                    if self.object.customer.vat_enabled:
                        item.tax_amount = (item.quantity * item.unit_price) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) + item.tax_amount
                    item.save()
                    
                    total += item.line_total
                    tax += item.tax_amount
                
                for obj in items.deleted_objects:
                    obj.delete()
                
                self.object.tax_amount = tax
                self.object.total_amount = total
                self.object.save()
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)

class QuotationUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Quotation
    form_class = QuotationForm
    template_name = 'sales/quotation_form.html'
    success_url = reverse_lazy('quotation_list')
    permission_required = 'sales.change_quotation'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = QuotationItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = QuotationItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                for item in saved_items:
                    item.quotation = self.object
                    if self.object.customer.vat_enabled:
                        item.tax_amount = (item.quantity * item.unit_price) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) + item.tax_amount
                    item.save()
                    
                # Re-calculate totals from ALL items associated with this quotation
                for item in self.object.items.all():
                    total += item.line_total
                    tax += item.tax_amount
                
                for obj in items.deleted_objects:
                    obj.delete()
                    total -= obj.line_total
                    tax -= obj.tax_amount
                
                self.object.tax_amount = tax
                self.object.total_amount = total
                self.object.save()
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)


class InvoiceCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'sales/invoice_form.html'
    success_url = reverse_lazy('invoice_list')
    permission_required = 'sales.add_invoice'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = InvoiceItemFormSet(self.request.POST)
        else:
            data['items'] = InvoiceItemFormSet()
            
        from users.models import User
        # Retrieve all active users who legitimately have permission to approve invoices.
        approving_users = [u for u in User.objects.filter(is_active=True) if u.has_perm('sales.approve_invoice') and u != self.request.user]
        data['approvers'] = approving_users
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save(commit=False)
            self.object.salesperson = self.request.user
            self.object.invoice_number = get_next_invoice_number()
            
            # Block or Mark for approval based on customer status
            if self.object.customer.customer_status in ['BLACKLIST', 'ONHOLD'] and not getattr(self.object, 'is_approved', False):
                if self.request.POST.get('is_approval_request') == 'true':
                    self.object.status = 'APPROVAL_PENDING'
                    approver_id = self.request.POST.get('designated_approver')
                    if approver_id:
                        from users.models import User
                        try:
                            self.object.designated_approver = User.objects.get(pk=approver_id)
                        except User.DoesNotExist:
                            pass
                else:
                    from django.core.exceptions import ValidationError
                    form.add_error(None, ValidationError(f"Invoice cannot be saved because customer is {self.object.customer.customer_status}."))
                    return super().form_invalid(form)
            
            if items.is_valid():
                self.object.save()
                items.instance = self.object
                
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                for item in saved_items:
                    item.invoice = self.object
                    if self.object.customer.vat_enabled:
                        item.tax_amount = (item.quantity * item.unit_price) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) + item.tax_amount
                    item.save()
                    
                    total += item.line_total
                    tax += item.tax_amount
                
                for obj in items.deleted_objects:
                    obj.delete()
                
                self.object.tax_amount = tax
                self.object.total_amount = total
                self.object.save()
                
                if getattr(self.object, 'status', None) == 'APPROVAL_PENDING':
                    send_invoice_approval_email(self.object, self.request)
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)

class InvoiceUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    model = Invoice
    form_class = InvoiceForm
    template_name = 'sales/invoice_form.html'
    success_url = reverse_lazy('invoice_list')
    permission_required = 'sales.change_invoice'

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = InvoiceItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = InvoiceItemFormSet(instance=self.object)
            
        from users.models import User
        approving_users = [u for u in User.objects.filter(is_active=True) if u.has_perm('sales.approve_invoice') and u != self.request.user]
        data['approvers'] = approving_users
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save(commit=False)
            
            # Block or Mark for approval based on customer status
            if self.object.customer.customer_status in ['BLACKLIST', 'ONHOLD'] and self.object.status == 'DRAFT' and not getattr(self.object, 'is_approved', False):
                if self.request.POST.get('is_approval_request') == 'true':
                    self.object.status = 'APPROVAL_PENDING'
                    approver_id = self.request.POST.get('designated_approver')
                    if approver_id:
                        from users.models import User
                        try:
                            self.object.designated_approver = User.objects.get(pk=approver_id)
                        except User.DoesNotExist:
                            pass
                else:
                    from django.core.exceptions import ValidationError
                    form.add_error(None, ValidationError(f"Invoice cannot be saved because customer is {self.object.customer.customer_status}."))
                    return super().form_invalid(form)
            
            self.object.save()

            if items.is_valid():
                items.instance = self.object
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                for item in saved_items:
                    item.invoice = self.object
                    if self.object.customer.vat_enabled:
                        item.tax_amount = (item.quantity * item.unit_price) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) + item.tax_amount
                    item.save()
                    
                # Re-calculate totals from ALL items
                for item in self.object.items.all():
                    total += item.line_total
                    tax += item.tax_amount
                
                for obj in items.deleted_objects:
                    obj.delete()
                    total -= obj.line_total
                    tax -= obj.tax_amount
                
                self.object.tax_amount = tax
                self.object.total_amount = total
                self.object.save()
                
                if getattr(self.object, 'status', None) == 'APPROVAL_PENDING':
                    send_invoice_approval_email(self.object, self.request)
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)

class QuotationExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sales.view_quotation'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="quotations.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Quotation Number', 'Customer', 'Creation Date', 'Salesperson', 'Valid Until', 'Total Amount'])
        
        quotations = Quotation.objects.filter(salesperson=self.request.user)
        q = request.GET.get('q')
        if q:
            quotations = quotations.filter(quotation_number__icontains=q)
            
        for q_obj in quotations:
            writer.writerow([q_obj.quotation_number, q_obj.customer.customer_name, q_obj.creation_date, q_obj.salesperson.username.title(), q_obj.valid_until, q_obj.total_amount])
            
        return response

class InvoiceExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sales.view_invoice'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Invoice Number', 'Type', 'Customer', 'Salesperson', 'Status', 'Delivery Date', 'Total Amount'])
        
        invoices = Invoice.objects.filter(salesperson=self.request.user)
        q = request.GET.get('q')
        if q:
            invoices = invoices.filter(invoice_number__icontains=q)
            
        for inv in invoices:
            writer.writerow([inv.invoice_number, inv.get_invoice_type_display(), inv.customer.customer_name, inv.salesperson.username.title(), inv.get_status_display(), inv.delivery_date, inv.total_amount])
            
        return response

import math

class InvoicePrintView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Invoice
    template_name = 'sales/invoice_print.html'
    context_object_name = 'invoice'
    permission_required = 'sales.view_invoice'

    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        if self.object.status == 'APPROVAL_PENDING':
            messages.error(request, "Cannot print an invoice that is pending approval.")
            return redirect('invoice_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Total Value of Supply = total_amount - tax_amount 
        subtotal = self.object.total_amount - self.object.tax_amount
        context['total_value_supply'] = math.ceil(subtotal)
        context['tax_amount'] = math.ceil(self.object.tax_amount)
        context['total_amount'] = math.ceil(self.object.total_amount)
        try:
            context['amount_in_words'] = num2words(context['total_amount'], lang='en').title() + " Rupees Only"
        except:
            context['amount_in_words'] = ""
        return context

class QuotationPrintView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = Quotation
    template_name = 'sales/quotation_print.html'
    context_object_name = 'quotation'
    permission_required = 'sales.view_quotation'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Total Value of Supply = total_amount - tax_amount
        subtotal = self.object.total_amount - self.object.tax_amount
        context['total_value_supply'] = math.ceil(subtotal)
        context['tax_amount'] = math.ceil(self.object.tax_amount)
        context['total_amount'] = math.ceil(self.object.total_amount)
        try:
            context['amount_in_words'] = num2words(context['total_amount'], lang='en').title() + " Rupees Only"
        except:
            context['amount_in_words'] = ""
        return context

@login_required
def confirm_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        try:
            issue_invoice(invoice, request.user)
            messages.success(request, f"Invoice {invoice.invoice_number} issued. Stock deducted.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('invoice_list')

@login_required
def cancel_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        try:
            cancel_invoice(invoice, request.user)
            messages.success(request, f"Invoice {invoice.invoice_number} cancelled. Stock restored.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('invoice_list')

@login_required
def approve_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not request.user.has_perm('sales.approve_invoice'):
        messages.error(request, "You do not have permission to approve invoices.")
        return redirect('invoice_list')
        
    if request.method == 'POST':
        if invoice.status == 'APPROVAL_PENDING':
            invoice.status = 'DRAFT'
            invoice.is_approved = True
            invoice.save(update_fields=['status', 'is_approved'])
            messages.success(request, f"Invoice {invoice.invoice_number} has been approved and moved to Draft.")
        else:
            messages.warning(request, "This invoice is not pending approval.")
    return redirect('invoice_list')

@login_required
def reject_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not request.user.has_perm('sales.approve_invoice'):
        messages.error(request, "You do not have permission to reject invoices.")
        return redirect('invoice_list')
        
    if request.method == 'POST':
        if invoice.status == 'APPROVAL_PENDING':
            invoice.status = 'CANCELLED'
            invoice.save(update_fields=['status'])
            messages.error(request, f"Invoice {invoice.invoice_number} has been rejected and cancelled.")
        else:
            messages.warning(request, "This invoice is not pending approval.")
    return redirect('invoice_list')
