from django.shortcuts import render, redirect, get_object_or_404
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, View, DetailView
from django.http import HttpResponse, JsonResponse
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from users.mixins import ERPPermissionRequiredMixin
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum, F
from decimal import Decimal, ROUND_UP, ROUND_HALF_UP
from .models import Quotation, Invoice, DeliveryNote, DeliveryNoteItem, SalesAuditLog, Return, CreditNote
from .forms import QuotationForm, QuotationItemFormSet, InvoiceForm, InvoiceItemFormSet, DeliveryNoteForm
from .services import issue_invoice, cancel_invoice, send_invoice_approval_email, log_sales_event, update_stock_reserves, process_return
from users.models import SavedFilter
from django.contrib.contenttypes.models import ContentType
import csv
import json
from datetime import timedelta
from django.db.models.functions import TruncDate
from num2words import num2words


from users.mixins import ERPUserPassesTestMixin
class AdminRequiredMixin(ERPUserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin()

class MainDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'sales/main_dashboard.html'

class SalesDashboardView(LoginRequiredMixin, ERPPermissionRequiredMixin, TemplateView):
    template_name = 'sales/dashboard.html'
    permission_required = 'sales.view_invoice'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from users.models import User
        from django.db.models import Q
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER, is_active=True).distinct()
        context['model_name'] = 'SalesDashboard'
        
        q = self.request.GET.get('q')
        
        today = timezone.now().date()
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        all_time = self.request.GET.get('all_time') == 'true'
        
        if all_time:
            date_from = None
            date_to = None
        elif not date_from and not date_to:
            date_from = today.strftime('%Y-%m-%d')
            date_to = today.strftime('%Y-%m-%d')
            
        salesperson_id = self.request.GET.get('salesperson')
        
        # Generate quick_months for Quick Select
        import calendar
        quick_months = []
        today_str = today.strftime('%Y-%m-%d')
        quick_months.append({
            'label': 'Today',
            'date_from': today_str,
            'date_to': today_str,
        })
        yesterday_str = (today - timezone.timedelta(days=1)).strftime('%Y-%m-%d')
        quick_months.append({
            'label': 'Yesterday',
            'date_from': yesterday_str,
            'date_to': yesterday_str,
        })
        for i in range(5):
            first_day = (today.replace(day=1) - timezone.timedelta(days=30 * i)).replace(day=1)
            last_day = calendar.monthrange(first_day.year, first_day.month)[1]
            last_date = first_day.replace(day=last_day)
            
            label = first_day.strftime('%b %Y')
            if i == 0:
                label = 'Current Month'
            elif i == 1:
                label = 'Last Month'

            quick_months.append({
                'label': label,
                'date_from': first_day.strftime('%Y-%m-%d'),
                'date_to': last_date.strftime('%Y-%m-%d'),
            })
        context['quick_months'] = quick_months
        
        # Pass the effective dates to context so the template knows what is active
        context['active_date_from'] = date_from
        context['active_date_to'] = date_to
        
        quotations = Quotation.objects.all()
        invoices = Invoice.objects.all()
        q = self.request.GET.get('q')
        status = self.request.GET.get('status')
        
        if q:
            quotations = quotations.filter(quotation_number__icontains=q)
            invoices = invoices.filter(invoice_number__icontains=q)
            
        if status:
            quotations = quotations.filter(status=status)
            invoices = invoices.filter(status=status)
            
        if date_from:
            quotations = quotations.filter(creation_date__date__gte=date_from)
            invoices = invoices.filter(creation_date__date__gte=date_from)
            
        if date_to:
            quotations = quotations.filter(creation_date__date__lte=date_to)
            invoices = invoices.filter(creation_date__date__lte=date_to)
            
        if salesperson_id:
            quotations = quotations.filter(salesperson_id=salesperson_id)
            invoices = invoices.filter(salesperson_id=salesperson_id)
            
        context['total_quotations_count'] = quotations.count()
        context['recent_quotations'] = quotations.order_by('-creation_date')[:15]
        context['recent_invoices'] = invoices.order_by('-creation_date')[:15]
        
        # Only include confirmed sales (ISSUED or PAID) for revenue stats
        active_invoices = invoices.filter(status__in=['ISSUED', 'PAID'])
        context['total_invoice_count'] = active_invoices.count()
        
        # Calculate gross revenue - use total_amount - tax_amount to correctly include converted quotation invoices
        revenue_with_vat = active_invoices.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
        revenue_ex_vat = sum(
            (inv.total_amount - inv.tax_amount) for inv in active_invoices.only('total_amount', 'tax_amount')
        )
        
        # Subtract Credit Notes (Returns)
        # Note: We filter credit notes by the same salesperson/date filters if applied to invoices
        credit_notes = CreditNote.objects.filter(original_invoice__in=active_invoices)
        total_credit = credit_notes.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        
        # Approximate tax for credit notes to subtract from Ex-VAT (based on original invoice customer VAT status)
        # For simplicity, we can sum the proportions or just use a reasonable estimation if tax isn't stored on CN
        # Here we'll just subtract the total credit from With-VAT and an estimated proportion from Ex-VAT
        # However, a better way is to sum (CN.quantity * CN.unit_price) which is effectively the subtotal.
        credit_subtotal = sum((cn.quantity * cn.unit_price) for cn in credit_notes)
        
        total_revenue_with_vat = revenue_with_vat - total_credit
        total_revenue_ex_vat = revenue_ex_vat - Decimal(str(credit_subtotal))
        
        context['total_revenue_with_vat'] = total_revenue_with_vat
        context['total_revenue_ex_vat'] = total_revenue_ex_vat
        
        # Calculate Average Daily Sales
        from django.db.models.functions import TruncDate
        days_recorded = active_invoices.annotate(d=TruncDate('creation_date')).values('d').distinct().count()
        if days_recorded == 0:
            days_recorded = 1
        
        context['days_recorded'] = days_recorded
        context['avg_daily_sales'] = float(total_revenue_ex_vat) / days_recorded
        
        sales_officers = context['sales_officers']
        
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='SalesDashboard')
        except ImportError:
            context['saved_filters'] = []
            
        # Determine target month/year from date_from or today
        target_date = timezone.now().date()
        if date_from:
            from datetime import datetime
            if isinstance(date_from, str):
                try:
                    target_date = datetime.strptime(date_from, '%Y-%m-%d').date()
                except ValueError:
                    pass
            else:
                target_date = date_from

        target_year = target_date.year
        target_month = target_date.month

        # Fetch Salesperson targets for this month
        from dashboard.models import SalespersonTarget
        sp_targets_map = {}
        for spt in SalespersonTarget.objects.filter(year=target_year, month=target_month):
            sp_targets_map[spt.salesperson_id] = spt.target_value

        # Calculate performance per Sales Officer
        officer_performance = []
        for officer in sales_officers:
            officer_invs = active_invoices.filter(salesperson=officer)
            officer_cns = credit_notes.filter(original_invoice__in=officer_invs)
            
            off_rev_with = officer_invs.aggregate(Sum('total_amount'))['total_amount__sum'] or Decimal('0.00')
            off_rev_ex = sum(
                (inv.total_amount - inv.tax_amount) for inv in officer_invs.only('total_amount', 'tax_amount')
            )
            
            off_cred = officer_cns.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
            off_cred_sub = sum((cn.quantity * cn.unit_price) for cn in officer_cns)
            
            net_with = off_rev_with - off_cred
            net_ex = Decimal(str(off_rev_ex)) - Decimal(str(off_cred_sub))

            
            sp_target_val = sp_targets_map.get(officer.id, Decimal('0.00'))
            
            target = sp_target_val
            if target > 0:
                progress_pct = min((net_ex / target) * 100, Decimal('100.00'))
            else:
                progress_pct = Decimal('0.00')
                
            if total_revenue_ex_vat > 0:
                contribution_pct = (net_ex / total_revenue_ex_vat) * Decimal('100')
            else:
                contribution_pct = Decimal('0.00')
                
            officer_performance.append({
                'officer': officer,
                'total_sales': net_with,
                'total_ex_vat': net_ex,
                'invoice_count': officer_invs.count(),
                'target': target,
                'progress_pct': progress_pct,
                'contribution_pct': contribution_pct
            })
        
        # Sort by total_ex_vat descending for leaderboard
        officer_performance.sort(key=lambda x: x['total_ex_vat'], reverse=True)
        context['officer_performance'] = officer_performance
        
        # --- Chart Data Generation ---
        
        # 1. Leaderboard Data (Bar Chart)
        # Using the sorted officer_performance list
        leaderboard_names = [perf['officer'].get_full_name() or perf['officer'].username for perf in officer_performance]
        leaderboard_sales = [float(perf['total_ex_vat']) for perf in officer_performance]
        leaderboard_targets = [float(perf['target']) for perf in officer_performance]
        context['leaderboard_names_json'] = json.dumps(leaderboard_names)
        context['leaderboard_sales_json'] = json.dumps(leaderboard_sales)
        context['leaderboard_targets_json'] = json.dumps(leaderboard_targets)
        context['target_month_name'] = target_date.strftime('%B %Y')
        
        # 1.5 Contribution Data (Doughnut Chart)
        contribution_names = [perf['officer'].get_full_name() or perf['officer'].username for perf in officer_performance if perf['total_ex_vat'] > 0]
        contribution_sales = [float(perf['total_ex_vat']) for perf in officer_performance if perf['total_ex_vat'] > 0]
        context['contribution_names_json'] = json.dumps(contribution_names)
        context['contribution_sales_json'] = json.dumps(contribution_sales)
        
        # 2. Revenue Trendline Data (Line Chart)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=29)
        
        trend_invoices = active_invoices
        if not date_from and not date_to:
            trend_invoices = trend_invoices.filter(creation_date__date__gte=start_date)
            
        daily_revenue = trend_invoices.annotate(
            date=TruncDate('creation_date'),
            ex_vat=F('total_amount') - F('tax_amount')
        ).values('date').annotate(
            daily_total=Sum('ex_vat')
        ).order_by('date')
        
        # To handle credit notes in trend, we can just map invoice creation date to revenue.
        # This is an approximation for trend line.
        revenue_dict = {str(item['date']): float(item['daily_total']) for item in daily_revenue}
        
        trend_dates = []
        trend_totals = []
        
        if date_from and date_to:
            # If explicit filters are set, just plot the available data points
            for item in daily_revenue:
                trend_dates.append(item['date'].strftime('%b %d'))
                trend_totals.append(float(item['daily_total']))
        else:
            # Default 30 days smooth line
            curr = start_date
            while curr <= end_date:
                trend_dates.append(curr.strftime('%b %d'))
                trend_totals.append(revenue_dict.get(str(curr), 0.0))
                curr += timedelta(days=1)
                
        context['trend_dates_json'] = json.dumps(trend_dates)
        context['trend_totals_json'] = json.dumps(trend_totals)
            
        return context

class QuotationListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = Quotation
    template_name = 'sales/quotation_list.html'
    context_object_name = 'quotations'
    paginate_by = 20
    permission_required = 'sales.view_quotation'
    
    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().order_by('-creation_date')

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
        from django.db.models import Q
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER, is_active=True).distinct()
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Quotation')
        except ImportError:
            context['saved_filters'] = []
        context['model_name'] = 'Quotation'
        return context

class InvoiceListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = Invoice
    template_name = 'sales/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    permission_required = 'sales.view_invoice'
    
    def get_queryset(self):
        from django.db.models import Q
        qs = super().get_queryset().order_by('-creation_date')

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

        is_returned = self.request.GET.get('is_returned')
        if is_returned == 'true':
            qs = qs.filter(status__in=['CANCELLED', 'CANCEL_PENDING'], cancellation_reason__icontains='Customer Return')

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from users.models import User
        from django.db.models import Q
        context['sales_officers'] = User.objects.filter(role=User.Roles.SALES_OFFICER, is_active=True).distinct()
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='Invoice')
        except ImportError:
            context['saved_filters'] = []
        context['model_name'] = 'Invoice'
        return context

class QuotationCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
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
            self.object.salesperson = self.object.customer.assigned_sales_officer or self.request.user
            # Quotation number is generated automatically in Quotation.save()
            
            if items.is_valid():
                self.object.save()
                items.instance = self.object
                
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                tot_discount = 0
                for item in saved_items:
                    item.quotation = self.object
                    discount_amt = item.get_discount_amount
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount_amt) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount_amt + item.tax_amount
                    item.save()
                    
                for obj in items.deleted_objects:
                    obj.delete()
                    
                # Calculate aggregated values for quotation
                gross_total = sum((item.quantity * item.unit_price) for item in self.object.items.all())
                line_discount = sum(item.get_discount_amount for item in self.object.items.all())
                subtotal = gross_total - line_discount
                
                custom_val = self.object.custom_discount_value or Decimal('0.00')
                if self.object.custom_discount_type == 'PERCENT':
                    global_discount = subtotal * (custom_val / Decimal('100.0'))
                else:
                    global_discount = custom_val
                    
                tot_discount = line_discount + global_discount
                subtotal -= global_discount
                if subtotal < Decimal('0.00'):
                    subtotal = Decimal('0.00')
                    
                if self.object.customer.vat_enabled:
                    tax = subtotal * Decimal('0.18')
                else:
                    tax = Decimal('0.00')
                
                total = subtotal + tax
                
                self.object.tax_amount = tax
                self.object.subtotal_amount = subtotal
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
            else:
                return super().form_invalid(form)
            
            
        log_sales_event(self.object, self.request.user, "Quotation Created", new_value=self.object.get_status_display())
        return super().form_valid(form)

class QuotationUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
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
            self.object = form.save(commit=False)
            if self.object.status == 'DRAFT':
                self.object.salesperson = self.object.customer.assigned_sales_officer or self.request.user
            self.object.save()
            if items.is_valid():
                items.instance = self.object
                saved_items = items.save(commit=False)
                
                total = 0
                tax = 0
                tot_discount = 0
                for item in saved_items:
                    item.quotation = self.object
                    discount_amt = item.get_discount_amount
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount_amt) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount_amt + item.tax_amount
                    item.save()
                    
                # Re-calculate totals from ALL items associated with this quotation
                gross_total = sum((item.quantity * item.unit_price) for item in self.object.items.all())
                line_discount = sum(item.get_discount_amount for item in self.object.items.all())
                subtotal = gross_total - line_discount
                
                custom_val = self.object.custom_discount_value or Decimal('0.00')
                if self.object.custom_discount_type == 'PERCENT':
                    global_discount = subtotal * (custom_val / Decimal('100.0'))
                else:
                    global_discount = custom_val
                    
                tot_discount = line_discount + global_discount
                subtotal -= global_discount
                if subtotal < Decimal('0.00'):
                    subtotal = Decimal('0.00')
                    
                if self.object.customer.vat_enabled:
                    tax = subtotal * Decimal('0.18')
                else:
                    tax = Decimal('0.00')
                
                total = subtotal + tax
                
                self.object.tax_amount = tax
                self.object.subtotal_amount = subtotal
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)


class InvoiceCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
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
            self.object.salesperson = self.object.customer.assigned_sales_officer or self.request.user
            self.object.created_by = self.request.user
            # Invoice number is generated automatically in Invoice.save()

            # ── Snapshot the selected delivery address ──────────────────────────
            self.object.snap_delivery_line1    = self.request.POST.get('snap_delivery_line1', '').strip() or None
            self.object.snap_delivery_line2    = self.request.POST.get('snap_delivery_line2', '').strip() or None
            self.object.snap_delivery_city     = self.request.POST.get('snap_delivery_city', '').strip() or None
            self.object.snap_delivery_province = self.request.POST.get('snap_delivery_province', '').strip() or None
            self.object.snap_delivery_zip      = self.request.POST.get('snap_delivery_zip', '').strip() or None
            # Fallback to customer's old single delivery address if nothing posted
            if not any([self.object.snap_delivery_line1, self.object.snap_delivery_city]):
                c = self.object.customer
                self.object.snap_delivery_line1    = c.delivery_address_line1
                self.object.snap_delivery_line2    = c.delivery_address_line2
                self.object.snap_delivery_city     = c.delivery_city
                self.object.snap_delivery_province = c.delivery_province
                self.object.snap_delivery_zip      = c.delivery_zip_code
            
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
                    discount_amt = item.get_discount_amount
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount_amt) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount_amt + item.tax_amount
                    item.save()
                    
                for obj in items.deleted_objects:
                    obj.delete()
                
                # Calculate aggregated values for invoice
                gross_total = sum((item.quantity * item.unit_price) for item in self.object.items.all())
                line_discount = sum(item.get_discount_amount for item in self.object.items.all())
                subtotal = gross_total - line_discount
                
                custom_val = self.object.custom_discount_value or Decimal('0.00')
                if self.object.custom_discount_type == 'PERCENT':
                    global_discount = subtotal * (custom_val / Decimal('100.0'))
                else:
                    global_discount = custom_val
                    
                tot_discount = line_discount + global_discount
                subtotal -= global_discount
                if subtotal < Decimal('0.00'):
                    subtotal = Decimal('0.00')
                    
                if self.object.customer.vat_enabled:
                    tax = subtotal * Decimal('0.18')
                else:
                    tax = Decimal('0.00')
                
                total = subtotal + tax
                
                self.object.tax_amount = tax
                self.object.subtotal_amount = subtotal
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

class InvoiceUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
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

            # Sync salesperson for DRAFT invoices
            if self.object.status == 'DRAFT':
                self.object.salesperson = self.object.customer.assigned_sales_officer or self.request.user
                # Allow updating snapshot address on DRAFT invoices
                if self.request.POST.get('snap_delivery_line1') or self.request.POST.get('snap_delivery_city'):
                    self.object.snap_delivery_line1    = self.request.POST.get('snap_delivery_line1', '').strip() or None
                    self.object.snap_delivery_line2    = self.request.POST.get('snap_delivery_line2', '').strip() or None
                    self.object.snap_delivery_city     = self.request.POST.get('snap_delivery_city', '').strip() or None
                    self.object.snap_delivery_province = self.request.POST.get('snap_delivery_province', '').strip() or None
                    self.object.snap_delivery_zip      = self.request.POST.get('snap_delivery_zip', '').strip() or None
            
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
                    discount_amt = item.get_discount_amount
                    if self.object.customer.vat_enabled:
                        item.tax_amount = ((item.quantity * item.unit_price) - discount_amt) * Decimal('0.18')
                    else:
                        item.tax_amount = Decimal('0.00')
                        
                    item.line_total = (item.quantity * item.unit_price) - discount_amt + item.tax_amount
                    item.save()
                    
                for obj in items.deleted_objects:
                    obj.delete()
                    
                # Calculate aggregated values for invoice
                gross_total = sum((item.quantity * item.unit_price) for item in self.object.items.all())
                line_discount = sum(item.get_discount_amount for item in self.object.items.all())
                subtotal = gross_total - line_discount
                
                custom_val = self.object.custom_discount_value or Decimal('0.00')
                if self.object.custom_discount_type == 'PERCENT':
                    global_discount = subtotal * (custom_val / Decimal('100.0'))
                else:
                    global_discount = custom_val
                    
                tot_discount = line_discount + global_discount
                subtotal -= global_discount
                if subtotal < Decimal('0.00'):
                    subtotal = Decimal('0.00')
                    
                if self.object.customer.vat_enabled:
                    tax = subtotal * Decimal('0.18')
                else:
                    tax = Decimal('0.00')
                
                total = subtotal + tax
                
                self.object.tax_amount = tax
                self.object.subtotal_amount = subtotal
                self.object.total_discount = tot_discount
                self.object.total_amount = total.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP).quantize(Decimal('1.'), rounding=ROUND_UP)
                self.object.save()
                
                update_stock_reserves(self.object)
                
                if getattr(self.object, 'status', None) == 'APPROVAL_PENDING':
                    send_invoice_approval_email(self.object, self.request)
            else:
                return super().form_invalid(form)
            
        return super().form_valid(form)

class QuotationExportView(LoginRequiredMixin, ERPPermissionRequiredMixin, View):
    permission_required = 'sales.view_quotation'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="quotations.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Quotation Number', 'Customer', 'Creation Date', 'Salesperson', 'Valid Until', 'Total Amount', 'Status'])
        
        quotations = Quotation.objects.all().order_by('-creation_date')
        q = request.GET.get('q')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        salesperson_id = request.GET.get('salesperson')
        status = request.GET.get('status')
        
        from django.db.models import Q
        if q:
            quotations = quotations.filter(
                Q(quotation_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )
        if date_from:
            quotations = quotations.filter(creation_date__date__gte=date_from)
        if date_to:
            quotations = quotations.filter(creation_date__date__lte=date_to)
        if salesperson_id:
            quotations = quotations.filter(salesperson_id=salesperson_id)
        if status:
            quotations = quotations.filter(status=status)
            
        for q_obj in quotations.order_by('-creation_date'):
            writer.writerow([q_obj.quotation_number, q_obj.customer.customer_name, q_obj.creation_date, q_obj.salesperson.username.title() if q_obj.salesperson else 'N/A', q_obj.valid_until, q_obj.total_amount, q_obj.get_status_display()])
            
        return response

class InvoiceExportView(LoginRequiredMixin, ERPPermissionRequiredMixin, View):
    permission_required = 'sales.view_invoice'
    
    def get(self, request, *args, **kwargs):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="invoices.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Invoice Number', 'Type', 'Customer', 'Salesperson', 'Status', 'Delivery Date', 'Total Amount'])
        
        invoices = Invoice.objects.all().order_by('-creation_date')
        q = request.GET.get('q')
        date_from = request.GET.get('date_from')
        date_to = request.GET.get('date_to')
        salesperson_id = request.GET.get('salesperson')
        status = request.GET.get('status')
        is_returned = request.GET.get('is_returned')
        
        from django.db.models import Q
        if q:
            invoices = invoices.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )
        if date_from:
            invoices = invoices.filter(creation_date__date__gte=date_from)
        if date_to:
            invoices = invoices.filter(creation_date__date__lte=date_to)
        if salesperson_id:
            invoices = invoices.filter(salesperson_id=salesperson_id)
        if status:
            invoices = invoices.filter(status=status)
        if is_returned == 'true':
            invoices = invoices.filter(status__in=['CANCELLED', 'CANCEL_PENDING'], cancellation_reason__icontains='Customer Return')
            
        for inv in invoices.order_by('-creation_date'):
            writer.writerow([inv.invoice_number, inv.get_invoice_type_display(), inv.customer.customer_name, inv.salesperson.username.title() if inv.salesperson else 'N/A', inv.get_status_display(), inv.delivery_date, inv.total_amount])
            
        return response

import math

class InvoicePrintView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
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

class QuotationPrintView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
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
            
        reason_type = request.POST.get('cancellation_reason_type', '')
        reason_text = request.POST.get('cancellation_reason', '')
        
        if reason_type == 'Other':
            reason = reason_text
        elif reason_type:
            reason = f"{reason_type}: {reason_text}" if reason_text else reason_type
        else:
            reason = reason_text
            
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
        
    if quotation.items.filter(product__isnull=True).exists():
        messages.error(request, "This quotation contains custom items. You must edit the quotation and link official products from the inventory before converting it to an invoice.")
        return redirect('quotation_list')
        
    with transaction.atomic():
        # Create Invoice Header
        invoice = Invoice.objects.create(
            customer=quotation.customer,
            salesperson=quotation.customer.assigned_sales_officer or request.user,
            total_amount=quotation.total_amount,
            subtotal_amount=quotation.subtotal_amount,
            tax_amount=quotation.tax_amount,
            total_discount=quotation.total_discount,
            custom_discount_type=quotation.custom_discount_type,
            custom_discount_value=quotation.custom_discount_value,
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
                discount_type=q_item.discount_type,
                discount=q_item.discount,
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

class DeliveryNoteListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
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
            qs = qs.filter(delivered_by_id=delivered_by)
            
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
        
        from users.models import User
        context['delivery_officers'] = User.objects.filter(is_active=True, is_delivery_officer=True)
        
        if self.request.user.is_authenticated:
            context['saved_filters'] = SavedFilter.objects.filter(
                user=self.request.user, 
                model_name='DeliveryNote'
            )
        else:
            context['saved_filters'] = []
        return context

class DeliveryNoteDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
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

class DeliveryNoteCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    model = DeliveryNote
    form_class = DeliveryNoteForm
    template_name = 'sales/delivery_note_form.html'
    permission_required = 'sales.add_deliverynote'

    def get_success_url(self):
        return reverse('delivery_note_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save(commit=False)
            invoice = self.object.invoice

            # Fix #8: Only allow DN creation against ISSUED invoices
            if invoice.status != 'ISSUED':
                form.add_error(
                    'invoice',
                    f"Delivery Notes can only be created for ISSUED invoices. "
                    f"'{invoice.invoice_number}' is currently {invoice.get_status_display()}."
                )
                return self.form_invalid(form)

            self.object.save()

            # Fix #9: Copy items with invoiced_quantity stored as a cap.
            # Delivery quantity is set to the full invoiced amount by default
            # (user can reduce it for partial delivery, but never exceed it).
            for item in invoice.items.all():
                DeliveryNoteItem.objects.create(
                    delivery_note=self.object,
                    product=item.product,
                    quantity=item.quantity,           # delivered qty (default = full)
                    invoiced_quantity=item.quantity,  # hard cap — never exceed this
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
    customer = invoice.customer

    # Use the invoice's own snapshotted delivery address if available.
    # Fall back to the customer's current address for backward compatibility.
    if invoice.snap_delivery_line1 or invoice.snap_delivery_city:
        addr_parts = [
            invoice.snap_delivery_line1,
            invoice.snap_delivery_line2,
            invoice.snap_delivery_city,
            invoice.snap_delivery_province,
            invoice.snap_delivery_zip,
        ]
    else:
        addr_parts = [
            customer.delivery_address_line1,
            customer.delivery_address_line2,
            customer.delivery_city,
            customer.delivery_province,
            customer.delivery_zip_code,
        ]
    address = ", ".join([p for p in addr_parts if p])

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


# ─────────────────────────────────────────────────────────────────────────────
# RETURNS & CREDIT NOTES
# ─────────────────────────────────────────────────────────────────────────────

class ReturnListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = Return
    template_name = 'sales/return_list.html'
    context_object_name = 'returns'
    paginate_by = 20
    permission_required = 'sales.view_return'

    def get_queryset(self):
        qs = Return.objects.select_related('original_invoice', 'returned_product', 'created_by').order_by('-created_date')
        q = self.request.GET.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(return_number__icontains=q) |
                Q(original_invoice__invoice_number__icontains=q) |
                Q(returned_product__name__icontains=q)
            )
        status = self.request.GET.get('status')
        if status == 'processed':
            qs = qs.filter(stock_updated=True)
        elif status == 'pending':
            qs = qs.filter(stock_updated=False)
        return qs


@login_required
@permission_required('sales.add_return', raise_exception=True)
def return_create_view(request, invoice_pk):
    """Create a Return against a specific ISSUED invoice."""
    invoice = get_object_or_404(Invoice, pk=invoice_pk)

    if invoice.status not in ['ISSUED', 'PAID']:
        messages.error(request, "Returns can only be raised against Issued or Paid invoices.")
        return redirect('invoice_list')

    if request.method == 'POST':
        product_id = request.POST.get('returned_product')
        quantity = int(request.POST.get('quantity', 0))
        unit_price = request.POST.get('unit_price', '0')
        reason = request.POST.get('reason')
        condition = request.POST.get('condition')
        notes = request.POST.get('notes', '')

        from inventory.models import Product
        product = get_object_or_404(Product, pk=product_id)

        if quantity <= 0:
            messages.error(request, "Quantity must be greater than zero.")
        else:
            ret = Return.objects.create(
                original_invoice=invoice,
                returned_product=product,
                quantity=quantity,
                unit_price=unit_price,
                reason=reason,
                condition=condition,
                notes=notes,
                created_by=request.user,
            )
            # Immediately process: restore stock + generate credit note
            try:
                credit_note = process_return(ret, request.user)
                messages.success(
                    request,
                    f"Return {ret.return_number} processed. Stock restored. "
                    f"Credit Note {credit_note.credit_note_number} issued (Rs {credit_note.credit_amount})."
                )
                return redirect('credit_note_print', pk=credit_note.pk)
            except Exception as e:
                messages.error(request, f"Error processing return: {e}")

    return render(request, 'sales/return_form.html', {
        'invoice': invoice,
        'invoice_items': invoice.items.select_related('product').all(),
        'return_reasons': Return.ReturnReason.choices,
        'conditions': Return.Condition.choices,
    })


class CreditNoteListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = CreditNote
    template_name = 'sales/credit_note_list.html'
    context_object_name = 'credit_notes'
    paginate_by = 20
    permission_required = 'sales.view_return'

    def get_queryset(self):
        qs = CreditNote.objects.select_related('customer', 'product', 'original_invoice').order_by('-issued_date')
        q = self.request.GET.get('q')
        if q:
            from django.db.models import Q
            qs = qs.filter(
                Q(credit_note_number__icontains=q) |
                Q(original_invoice__invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )
        return qs


@login_required
def credit_note_print_view(request, pk):
    """Printable Credit Note view."""
    cn = get_object_or_404(CreditNote, pk=pk)
    return render(request, 'sales/credit_note_print.html', {'cn': cn})

