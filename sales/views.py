from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View, DetailView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin, PermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from .models import Quotation, Invoice, DeliveryNote, DeliveryNoteItem, SalesAuditLog
from .forms import QuotationForm, QuotationItemFormSet, InvoiceForm, InvoiceItemFormSet, DeliveryNoteForm
from .services import issue_invoice, cancel_invoice, send_invoice_approval_email, log_sales_event, update_stock_reserves
from users.models import SavedFilter
from django.contrib.contenttypes.models import ContentType
import csv
from num2words import num2words

def get_next_invoice_number():
    prefix = timezone.now().strftime('%y%b').upper() + "_EBFR_"
    # Find the maximum number across ALL invoices to ensure continuity
    existing = Invoice.objects.all().values_list('invoice_number', flat=True)
    used = []
    for num in existing:
        try:
            parts = num.split('_')
            if parts:
                used.append(int(parts[-1]))
        except (ValueError, IndexError):
            pass
    
    start_num = 315
    next_num = start_num
    while next_num in used:
        next_num += 1
    return f"{prefix}{next_num:05d}"
    
def get_next_quotation_number():
    prefix = timezone.now().strftime('%y%b').upper() + "_EBFR_QUO_"
    # Find the maximum number across ALL quotations to ensure continuity
    existing = Quotation.objects.all().values_list('quotation_number', flat=True)
    used = []
    for num in existing:
        try:
            parts = num.split('_')
            if parts:
                used.append(int(parts[-1]))
        except (ValueError, IndexError):
            pass
            
    start_num = 484
    next_num = start_num
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
        from users.models import User
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER)
        context['model_name'] = 'SalesDashboard'
        
        q = self.request.GET.get('q')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        salesperson_id = self.request.GET.get('salesperson')
        
        if self.request.user.role == 'SALES_OFFICER':
            quotations = Quotation.objects.filter(salesperson=self.request.user)
            invoices = Invoice.objects.filter(salesperson=self.request.user)
        else:
            quotations = Quotation.objects.all()
            invoices = Invoice.objects.all()
        
        if q:
            quotations = quotations.filter(quotation_number__icontains=q)
            invoices = invoices.filter(invoice_number__icontains=q)
            
        if date_from:
            quotations = quotations.filter(creation_date__gte=date_from)
            invoices = invoices.filter(creation_date__gte=date_from)
            
        if date_to:
            quotations = quotations.filter(creation_date__lte=date_to)
            invoices = invoices.filter(creation_date__lte=date_to)
            
        if salesperson_id:
            quotations = quotations.filter(salesperson_id=salesperson_id)
            invoices = invoices.filter(salesperson_id=salesperson_id)
            
        context['recent_quotations'] = quotations.order_by('-creation_date')[:15]
        context['recent_invoices'] = invoices.order_by('-creation_date')[:15]
        
        # Exclude cancelled invoices from the total amount stat
        active_invoices = invoices.exclude(status='CANCELLED')
        context['total_invoice_count'] = active_invoices.count()
        context['total_invoice_amount'] = active_invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        return context

class QuotationListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Quotation
    template_name = 'sales/quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20
    permission_required = 'sales.view_quotation'
    
    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().order_by('-creation_date')
        if self.request.user.role == 'SALES_OFFICER':
            qs = qs.filter(salesperson=self.request.user)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(creation_date__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(creation_date__date__lte=date_to)

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(quotation_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )

        salesperson_id = self.request.GET.get('salesperson')
        if salesperson_id:
            qs = qs.filter(salesperson_id=salesperson_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from users.models import User
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER)
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Quotation')
        except ImportError:
            context['saved_filters'] = []
        context['model_name'] = 'Quotation'
        return context

class InvoiceListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = Invoice
    template_name = 'sales/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    permission_required = 'sales.view_invoice'
    
    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().order_by('-creation_date')
        if self.request.user.role == 'SALES_OFFICER':
            qs = qs.filter(salesperson=self.request.user)

        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)

        date_from = self.request.GET.get('date_from')
        if date_from:
            qs = qs.filter(creation_date__date__gte=date_from)

        date_to = self.request.GET.get('date_to')
        if date_to:
            qs = qs.filter(creation_date__date__lte=date_to)

        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )

        salesperson_id = self.request.GET.get('salesperson')
        if salesperson_id:
            qs = qs.filter(salesperson_id=salesperson_id)

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from users.models import User
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER)
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Invoice')
        except ImportError:
            context['saved_filters'] = []
        context['model_name'] = 'Invoice'
        return context

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
                tot_discount = 0
                for item in saved_items:
                    item.quotation = self.object
                    discount = item.discount or Decimal('0.00')
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount + item.tax_amount
                    item.save()
                    
                    total += item.line_total
                    tax += item.tax_amount
                    tot_discount += discount
                
                for obj in items.deleted_objects:
                    obj.delete()
                
                self.object.tax_amount = tax
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
            else:
                return super().form_invalid(form)
            
            
        log_sales_event(self.object, self.request.user, "Quotation Created", new_value=self.object.get_status_display())
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
        
        from .models import SalesAuditLog
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Quotation)
        data['audit_logs'] = SalesAuditLog.objects.filter(content_type=ct, object_id=self.object.id).order_by('-timestamp')
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
                tot_discount = 0
                for item in saved_items:
                    item.quotation = self.object
                    discount = item.discount or Decimal('0.00')
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount + item.tax_amount
                    item.save()
                    
                # Re-calculate totals from ALL items associated with this quotation
                for item in self.object.items.all():
                    total += item.line_total
                    tax += item.tax_amount
                    tot_discount += item.discount or Decimal('0.00')
                
                for obj in items.deleted_objects:
                    obj.delete()
                    total -= obj.line_total
                    tax -= obj.tax_amount
                    tot_discount -= obj.discount or Decimal('0.00')
                
                self.object.tax_amount = tax
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
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
                tot_discount = 0
                for item in saved_items:
                    item.invoice = self.object
                    discount = item.discount or Decimal('0.00')
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount + item.tax_amount
                    item.save()
                    
                    total += item.line_total
                    tax += item.tax_amount
                    tot_discount += discount
                
                for obj in items.deleted_objects:
                    obj.delete()
                
                self.object.tax_amount = tax
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
                
                log_sales_event(
                    obj=self.object,
                    user=self.request.user,
                    action="Invoice Created",
                    new_value=self.object.get_status_display(),
                    notes=f"Initial creation. Approver: {self.object.designated_approver}" if self.object.status == 'APPROVAL_PENDING' else None
                )
                
                update_stock_reserves(self.object)
                
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
        
        from .models import SalesAuditLog
        from django.contrib.contenttypes.models import ContentType
        ct = ContentType.objects.get_for_model(Invoice)
        data['audit_logs'] = SalesAuditLog.objects.filter(content_type=ct, object_id=self.object.id).order_by('-timestamp')
        
        # Add cancellation approvers based on permission
        data['cancellation_approvers'] = [u for u in User.objects.filter(is_active=True) if u.has_perm('sales.approve_invoice')]
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save(commit=False)
            
            if self.object.pk and self.object.status != 'DRAFT':
                from django.core.exceptions import ValidationError
                form.add_error(None, ValidationError("Only DRAFT invoices can be edited and saved."))
                return super().form_invalid(form)
            
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
                tot_discount = 0
                for item in saved_items:
                    item.invoice = self.object
                    discount = item.discount or Decimal('0.00')
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount + item.tax_amount
                    item.save()
                    
                # Re-calculate totals from ALL items
                for item in self.object.items.all():
                    total += item.line_total
                    tax += item.tax_amount
                    tot_discount += item.discount or Decimal('0.00')
                
                for obj in items.deleted_objects:
                    obj.delete()
                    total -= obj.line_total
                    tax -= obj.tax_amount
                    tot_discount -= obj.discount or Decimal('0.00')
                
                self.object.tax_amount = tax
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
                
                update_stock_reserves(self.object)
                
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
        
        if not request.user.has_perm('sales.approve_invoice'):
            quotations = Quotation.objects.filter(salesperson=self.request.user)
        else:
            quotations = Quotation.objects.all()

        q = request.GET.get('q')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        salesperson_id = request.GET.get('salesperson')
        
        if q:
            quotations = quotations.filter(quotation_number__icontains=q)
        if date_from:
            quotations = quotations.filter(creation_date__gte=date_from)
        if date_to:
            quotations = quotations.filter(creation_date__lte=date_to)
        if salesperson_id:
            quotations = quotations.filter(salesperson_id=salesperson_id)
            
        for q_obj in quotations.order_by('-creation_date'):
            writer.writerow([q_obj.quotation_number, q_obj.customer.customer_name, q_obj.creation_date, q_obj.salesperson.username.title() if q_obj.salesperson else 'N/A', q_obj.valid_until, q_obj.total_amount])
            
        return response

class InvoiceExportView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'sales.view_invoice'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Invoice Number', 'Type', 'Customer', 'Salesperson', 'Status', 'Delivery Date', 'Total Amount'])
        
        if not request.user.has_perm('sales.approve_invoice'):
            invoices = Invoice.objects.filter(salesperson=self.request.user)
        else:
            invoices = Invoice.objects.all()

        q = request.GET.get('q')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        salesperson_id = request.GET.get('salesperson')
        
        if q:
            invoices = invoices.filter(invoice_number__icontains=q)
        if date_from:
            invoices = invoices.filter(creation_date__gte=date_from)
        if date_to:
            invoices = invoices.filter(creation_date__lte=date_to)
        if salesperson_id:
            invoices = invoices.filter(salesperson_id=salesperson_id)
            
        for inv in invoices.order_by('-creation_date'):
            writer.writerow([inv.invoice_number, inv.get_invoice_type_display(), inv.customer.customer_name, inv.salesperson.username.title() if inv.salesperson else 'N/A', inv.get_status_display(), inv.delivery_date, inv.total_amount])
            
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
        if invoice.status != 'ISSUED':
            messages.error(request, "Only Issued invoices can be cancelled.")
            return redirect('invoice_list')
            
        reason = request.POST.get('cancellation_reason')
        approver_id = request.POST.get('designated_approver')
        if not reason or not approver_id:
            messages.error(request, "Reason and Approver are required.")
            return redirect('invoice_list')
            
        from users.models import User
        try:
            approver = User.objects.get(pk=approver_id)
        except User.DoesNotExist:
            messages.error(request, "Invalid approver selected.")
            return redirect('invoice_list')

        old_status = invoice.get_status_display()
        invoice.status = 'CANCEL_PENDING'
        invoice.cancellation_reason = reason
        invoice.designated_approver = approver
        invoice.save(update_fields=['status', 'cancellation_reason', 'designated_approver'])
        
        log_sales_event(
            obj=invoice,
            user=request.user,
            action="Cancellation Requested",
            old_value=old_status,
            new_value="Cancellation Pending",
            notes=f"Requested by {request.user.get_full_name()}. Reason: {reason}. Assigned to: {approver.get_full_name()}"
        )
        
        # Notify the specific approver
        from users.models import Notification
        Notification.objects.create(
            recipient=approver,
            title="Cancellation Approval Required",
            message=f"Cancellation requested for Invoice {invoice.invoice_number} by {request.user.get_full_name()}.",
            link=reverse('invoice_list')
        )
            
        messages.success(request, f"Cancellation request for {invoice.invoice_number} has been sent to {approver.get_full_name()} for approval.")
    return redirect('invoice_list')

@login_required
def request_edit_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if request.method == 'POST':
        if invoice.status != 'ISSUED':
            messages.error(request, "Only Issued invoices can be edited.")
            return redirect('invoice_list')
            
        reason = request.POST.get('cancellation_reason')
        approver_id = request.POST.get('designated_approver')
        if not reason or not approver_id:
            messages.error(request, "Reason and Approver are required.")
            return redirect('invoice_list')
            
        from users.models import User
        try:
            approver = User.objects.get(pk=approver_id)
        except User.DoesNotExist:
            messages.error(request, "Invalid approver selected.")
            return redirect('invoice_list')

        old_status = invoice.get_status_display()
        invoice.status = 'EDIT_PENDING'
        invoice.cancellation_reason = reason
        invoice.designated_approver = approver
        invoice.save(update_fields=['status', 'cancellation_reason', 'designated_approver'])
        
        log_sales_event(
            obj=invoice,
            user=request.user,
            action="Edit Requested",
            old_value=old_status,
            new_value="Edit Pending",
            notes=f"Requested by {request.user.get_full_name()}. Reason: {reason}. Assigned to: {approver.get_full_name()}"
        )
        
        from users.models import Notification
        Notification.objects.create(
            recipient=approver,
            title="Edit Approval Required",
            message=f"Edit requested for Invoice {invoice.invoice_number} by {request.user.get_full_name()}.",
            link=reverse('invoice_list')
        )
            
        messages.success(request, f"Edit request for {invoice.invoice_number} has been sent to {approver.get_full_name()} for approval.")
    return redirect('invoice_list')

@login_required
def approve_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not request.user.has_perm('sales.approve_invoice'):
        messages.error(request, "You do not have permission to approve invoices.")
        return redirect('invoice_list')
        
    if request.method == 'POST':
        reviewer_notes = request.POST.get('reviewer_notes', '')
        
        if invoice.status == 'APPROVAL_PENDING':
            old_status = invoice.get_status_display()
            invoice.status = 'DRAFT'
            invoice.is_approved = True
            invoice.reviewer_notes = reviewer_notes
            invoice.save(update_fields=['status', 'is_approved', 'reviewer_notes'])
            
            log_sales_event(
                obj=invoice,
                user=request.user,
                action="Invoice Approved",
                old_value=old_status,
                new_value=invoice.get_status_display(),
                notes=f"Manager Notes: {reviewer_notes}"
            )
            
            # Notify creator
            from users.models import Notification
            if invoice.salesperson:
                msg = f"Your invoice {invoice.invoice_number} has been approved."
                if reviewer_notes:
                    msg += f" Manager Notes: {reviewer_notes}"
                
                Notification.objects.create(
                    recipient=invoice.salesperson,
                    title="Invoice Approved",
                    message=msg,
                    link=reverse('invoice_edit', kwargs={'pk': invoice.pk})
                )
            
            messages.success(request, f"Invoice {invoice.invoice_number} has been approved and moved to Draft.")
            
        elif invoice.status == 'CANCEL_PENDING':
            # Check for permissions for cancellation approval
            if not request.user.has_perm('sales.approve_invoice'):
                messages.error(request, "You do not have permission to approve cancellations.")
                return redirect('invoice_list')
                
            old_status = invoice.get_status_display()
            try:
                from .services import cancel_invoice as service_cancel_invoice
                service_cancel_invoice(invoice, request.user)
                invoice.reviewer_notes = reviewer_notes
                invoice.save(update_fields=['reviewer_notes'])
                
                log_sales_event(
                    obj=invoice,
                    user=request.user,
                    action="Cancellation Approved",
                    old_value=old_status,
                    new_value="Cancelled",
                    notes=f"Manager Notes: {reviewer_notes}"
                )
                
                # Notify creator
                from users.models import Notification
                if invoice.salesperson:
                    msg = f"Invoice {invoice.invoice_number} cancellation has been approved. Stock restored."
                    if reviewer_notes:
                        msg += f" Manager Notes: {reviewer_notes}"
                        
                    Notification.objects.create(
                        recipient=invoice.salesperson,
                        title="Cancellation Approved",
                        message=msg,
                        link=reverse('invoice_list')
                    )
                
                messages.success(request, f"Cancellation for {invoice.invoice_number} has been approved. Stock has been restored.")
            except Exception as e:
                messages.error(request, f"Error during cancellation: {str(e)}")
                
        elif invoice.status == 'EDIT_PENDING':
            # Check for permissions for edit approval
            if not request.user.has_perm('sales.approve_invoice'):
                messages.error(request, "You do not have permission to approve edits.")
                return redirect('invoice_list')
                
            old_status = invoice.get_status_display()
            try:
                from .services import restore_stock
                # Use restore_stock to update inventory without setting status to CANCELLED
                restore_stock(invoice, request.user, "Edit Approved (Stock Restored)")
                
                invoice.status = 'DRAFT'
                invoice.reviewer_notes = reviewer_notes
                invoice.cancellation_reason = ''  # Clear reason
                invoice.save(update_fields=['status', 'reviewer_notes', 'cancellation_reason'])
                
                log_sales_event(
                    obj=invoice,
                    user=request.user,
                    action="Edit Approved",
                    old_value=old_status,
                    new_value="Draft",
                    notes=f"Stock restored. Manager Notes: {reviewer_notes}"
                )
                
                # Notify creator
                from users.models import Notification
                if invoice.salesperson:
                    msg = f"Invoice {invoice.invoice_number} edit has been approved. It is now a Draft and stock is restored."
                    if reviewer_notes:
                        msg += f" Manager Notes: {reviewer_notes}"

                    Notification.objects.create(
                        recipient=invoice.salesperson,
                        title="Edit Approved",
                        message=msg,
                        link=reverse('invoice_edit', kwargs={'pk': invoice.pk})
                    )
                
                messages.success(request, f"Edit for {invoice.invoice_number} has been approved. Stock restored and invoice is now a Draft.")
            except Exception as e:
                messages.error(request, f"Error during edit approval: {str(e)}")
        else:
            messages.warning(request, "This invoice is not pending any approval.")
    return redirect('invoice_list')

@login_required
def reject_invoice_view(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not request.user.has_perm('sales.approve_invoice'):
        messages.error(request, "You do not have permission to reject invoices.")
        return redirect('invoice_list')
        
    if request.method == 'POST':
        reviewer_notes = request.POST.get('reviewer_notes', '')
        
        if invoice.status == 'APPROVAL_PENDING':
            old_status = invoice.get_status_display()
            invoice.status = 'DRAFT' # Correct: Back to Draft for salesperson to fix or issue
            invoice.is_approved = False # Still not approved if rejected
            invoice.reviewer_notes = reviewer_notes
            invoice.save(update_fields=['status', 'is_approved', 'reviewer_notes'])
            
            log_sales_event(
                obj=invoice,
                user=request.user,
                action="Invoice Rejected",
                old_value=old_status,
                new_value=invoice.get_status_display(),
                notes=f"Manager Notes: {reviewer_notes}"
            )
            
            # Notify creator
            from users.models import Notification
            if invoice.salesperson:
                msg = f"Your invoice {invoice.invoice_number} has been rejected."
                if reviewer_notes:
                    msg += f" Manager Notes: {reviewer_notes}"
                else:
                    msg += " No reason provided."

                Notification.objects.create(
                    recipient=invoice.salesperson,
                    title="Invoice Rejected",
                    message=msg,
                    link=reverse('invoice_edit', kwargs={'pk': invoice.pk})
                )
            
            messages.warning(request, f"Invoice {invoice.invoice_number} has been rejected and moved back to Draft.")
            
        elif invoice.status == 'CANCEL_PENDING':
            # Check for permissions for cancellation rejection
            if not request.user.has_perm('sales.approve_invoice'):
                messages.error(request, "You do not have permission to reject cancellations.")
                return redirect('invoice_list')
                
            old_status = invoice.get_status_display()
            invoice.status = 'ISSUED' # Return to Issued
            invoice.reviewer_notes = reviewer_notes
            invoice.save(update_fields=['status', 'reviewer_notes'])
            
            log_sales_event(
                obj=invoice,
                user=request.user,
                action="Cancellation Rejected",
                old_value=old_status,
                new_value="Issued",
                notes=f"Manager Notes: {reviewer_notes}"
            )
            
            # Notify creator
            from users.models import Notification
            if invoice.salesperson:
                msg = f"Cancellation request for Invoice {invoice.invoice_number} was rejected. Status returned to Issued."
                if reviewer_notes:
                    msg += f" Manager Notes: {reviewer_notes}"

                Notification.objects.create(
                    recipient=invoice.salesperson,
                    title="Cancellation Rejected",
                    message=msg,
                    link=reverse('invoice_list')
                )
                
            messages.warning(request, f"Cancellation request for {invoice.invoice_number} has been rejected.")
            
        elif invoice.status == 'EDIT_PENDING':
            # Check for permissions for edit rejection
            if not request.user.has_perm('sales.approve_invoice'):
                messages.error(request, "You do not have permission to reject edits.")
                return redirect('invoice_list')
                
            old_status = invoice.get_status_display()
            invoice.status = 'ISSUED' # Return to Issued
            invoice.reviewer_notes = reviewer_notes
            invoice.cancellation_reason = ''
            invoice.save(update_fields=['status', 'reviewer_notes', 'cancellation_reason'])
            
            log_sales_event(
                obj=invoice,
                user=request.user,
                action="Edit Rejected",
                old_value=old_status,
                new_value="Issued",
                notes=f"Manager Notes: {reviewer_notes}"
            )
            
            from users.models import Notification
            if invoice.salesperson:
                msg = f"Edit request for Invoice {invoice.invoice_number} was rejected. The invoice remains in Issued status."
                if reviewer_notes:
                    msg += f" Manager Reason: {reviewer_notes}"

                Notification.objects.create(
                    recipient=invoice.salesperson,
                    title="Edit Request Denied",
                    message=msg,
                    link=reverse('invoice_list')
                )
                
            messages.warning(request, f"Edit request for {invoice.invoice_number} has been rejected.")
        else:
            messages.warning(request, "This invoice is not pending any approval.")
            
    return redirect('invoice_list')

@login_required
def quotation_mark_sent_view(request, pk):
    """Mark a DRAFT quotation as SENT (i.e. delivered to customer)."""
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        if quotation.status == 'DRAFT':
            old_status = quotation.get_status_display()
            quotation.status = 'SENT'
            quotation.save(update_fields=['status'])
            
            log_sales_event(
                obj=quotation,
                user=request.user,
                action="Quotation Sent",
                old_value=old_status,
                new_value=quotation.get_status_display()
            )
            
            messages.success(request, f"Quotation {quotation.quotation_number} marked as Sent.")
        else:
            messages.warning(request, "Only DRAFT quotations can be marked as Sent.")
    return redirect('quotation_list')

@login_required
def quotation_cancel_view(request, pk):
    """Cancel a DRAFT or SENT quotation."""
    quotation = get_object_or_404(Quotation, pk=pk)
    if request.method == 'POST':
        if quotation.status in ['DRAFT', 'SENT']:
            old_status = quotation.get_status_display()
            quotation.status = 'CANCELLED'
            quotation.save(update_fields=['status'])
            
            log_sales_event(
                obj=quotation,
                user=request.user,
                action="Quotation Cancelled",
                old_value=old_status,
                new_value=quotation.get_status_display()
            )
            
            messages.success(request, f"Quotation {quotation.quotation_number} cancelled.")
        else:
            messages.warning(request, "Only DRAFT or SENT quotations can be cancelled.")
    return redirect('quotation_list')


@login_required
@permission_required('sales.add_invoice', raise_exception=True)
def convert_quotation_view(request, pk):
    """Converts a Quotation into a Draft Invoice."""
    quotation = get_object_or_404(Quotation, pk=pk)
    
    if quotation.is_converted:
        messages.warning(request, "This quotation has already been converted to an invoice.")
        return redirect('quotation_list')
        
    with transaction.atomic():
        # Create Invoice Header
        invoice = Invoice.objects.create(
            customer=quotation.customer,
            salesperson=request.user,
            invoice_number=get_next_invoice_number(),
            total_amount=quotation.total_amount,
            tax_amount=quotation.tax_amount,
            notes=f"Converted from Quotation {quotation.quotation_number}. " + (quotation.notes or ""),
            status='DRAFT'
        )
        
        # Create Invoice Items
        from .models import InvoiceItem
        for q_item in quotation.items.all():
            InvoiceItem.objects.create(
                invoice=invoice,
                product=q_item.product,
                quantity=q_item.quantity,
                unit_price=q_item.unit_price,
                tax_amount=q_item.tax_amount,
                line_total=q_item.line_total
            )
            
        # Update Quotation status
        quotation.status = 'CONVERTED'
        quotation.is_converted = True
        quotation.save(update_fields=['status', 'is_converted'])
        
        log_sales_event(
            obj=quotation,
            user=request.user,
            action="Converted to Invoice",
            new_value=invoice.invoice_number
        )
        
        log_sales_event(
            obj=invoice,
            user=request.user,
            action="Created from Quotation",
            old_value=quotation.quotation_number
        )
        
        messages.success(request, f"Quotation {quotation.quotation_number} converted to Invoice {invoice.invoice_number} successfully.")
        return redirect('invoice_edit', pk=invoice.pk)

from django.http import JsonResponse

@login_required
def customer_search_ajax(request):
    """API endpoint for Select2 AJAX customer search."""
    q = request.GET.get('q', '')
    customers = Customer.objects.filter(
        Q(customer_name__icontains=q) | 
        Q(company_name__icontains=q) |
        Q(phone_number__icontains=q)
    )[:20]
    
    results = [
        {'id': c.id, 'text': f"{c.customer_name} ({c.company_name or 'No Company'})"} 
        for c in customers
    ]
    return JsonResponse({'results': results})

@login_required
def product_search_ajax(request):
    """API endpoint for Select2 AJAX product search."""
    q = request.GET.get('q', '')
    products = Product.objects.filter(
        Q(name__icontains=q) | 
        Q(product_id__icontains=q)
    )[:20]
    
    results = [
        {
            'id': p.id, 
            'text': f"[{p.product_id}] {p.name}",
            'price': float(p.selling_price),
            'stock': float(p.available_stock)
        } 
        for p in products
    ]
    return JsonResponse({'results': results})

class DeliveryNoteListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    model = DeliveryNote
    template_name = 'sales/delivery_note_list.html'
    context_object_name = 'delivery_notes'
    paginate_by = 20
    permission_required = 'sales.view_deliverynote'
    
    def get_queryset(self):
        qs = super().get_queryset().order_by('-created_at')
        
        # Status Filter
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        
        # Delivered By Filter
        delivered_by = self.request.GET.get('delivered_by')
        if delivered_by:
            qs = qs.filter(delivered_by=delivered_by)
            
        # Date Range Filter
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        if date_from:
            qs = qs.filter(created_at__date__gte=date_from)
        if date_to:
            qs = qs.filter(created_at__date__lte=date_to)

        # Unified Search (DN Details, Invoice, Customer)
        q = self.request.GET.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(dn_number__icontains=q) |
                Q(invoice__invoice_number__icontains=q) |
                Q(customer_name__icontains=q)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'DeliveryNote'
        if self.request.user.is_authenticated:
            context['saved_filters'] = SavedFilter.objects.filter(
                user=self.request.user, 
                model_name='DeliveryNote'
            )
        else:
            context['saved_filters'] = []
        return context

class DeliveryNoteDetailView(LoginRequiredMixin, PermissionRequiredMixin, DetailView):
    model = DeliveryNote
    template_name = 'sales/delivery_note_detail.html'
    context_object_name = 'dn'
    permission_required = 'sales.view_deliverynote'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ct = ContentType.objects.get_for_model(DeliveryNote)
        context['dn_audit_history'] = SalesAuditLog.objects.filter(
            content_type=ct, 
            object_id=self.object.id
        ).order_by('-timestamp')
        return context

class DeliveryNoteCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    model = DeliveryNote
    form_class = DeliveryNoteForm
    template_name = 'sales/delivery_note_form.html'
    permission_required = 'sales.add_deliverynote'

    def get_success_url(self):
        return reverse('delivery_note_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            # Copy items from invoice to DN items
            invoice = self.object.invoice
            for item in invoice.items.all():
                DeliveryNoteItem.objects.create(
                    delivery_note=self.object,
                    product=item.product,
                    quantity=item.quantity
                )
            messages.success(self.request, f"Delivery Note {self.object.dn_number} created successfully.")
            
            log_sales_event(
                obj=self.object,
                user=self.request.user,
                action="Delivery Note Created",
                new_value=self.object.get_status_display(),
                notes=f"Linked to Invoice {invoice.invoice_number}"
            )
            
            return super().form_valid(form)

@login_required
def get_invoice_details(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    # Concatenate delivery address
    customer = invoice.customer
    address_parts = [
        customer.delivery_address_line1,
        customer.delivery_address_line2,
        customer.delivery_city,
        customer.delivery_province,
        customer.delivery_zip_code
    ]
    address = ", ".join([p for p in address_parts if p])
    
    items = []
    for item in invoice.items.all():
        items.append({
            'product_name': item.product.name,
            'quantity': str(item.quantity),
            'product_id': item.product.product_id
        })
        
    data = {
        'customer_name': customer.company_name or customer.customer_name,
        'delivery_address': address,
        'delivery_date': invoice.delivery_date.isoformat() if invoice.delivery_date else '',
        'items': items
    }
    return JsonResponse(data)

@login_required
def update_dn_status(request, pk):
    dn = get_object_or_404(DeliveryNote, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(DeliveryNote.Status.choices):
            old_display = dn.get_status_display()
            dn.status = new_status
            dn.save()
            
            log_sales_event(
                obj=dn,
                user=request.user,
                action="Status Updated",
                old_value=old_display,
                new_value=dn.get_status_display(),
                notes=f"Manual status change from list/detail view."
            )
            
            messages.success(request, f"Status of {dn.dn_number} updated to {dn.get_status_display()}.")
    return redirect('delivery_note_list')
