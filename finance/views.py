import json
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Q, F
from django.db import transaction

from sales.models import Invoice
from .models import Payment

class FinanceDashboardView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/dashboard.html'

    def get(self, request):
        today = timezone.now().date()
        
        # We consider overdue: ISSUED status, not CASH/COD, due_date < today
        overdue_invoices = Invoice.objects.filter(
            status=Invoice.Status.ISSUED,
            due_date__lt=today
        ).exclude(invoice_type__in=['CASH', 'COD'])
        
        overdue_count = overdue_invoices.count()
        overdue_total = sum(inv.total_amount for inv in overdue_invoices)
        
        context = {
            'overdue_count': overdue_count,
            'overdue_total': overdue_total,
        }
        return render(request, self.template_name, context)

class OverdueInvoicesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/overdue_invoices.html'

    def get(self, request):
        today = timezone.now().date()
        
        overdue_qs = Invoice.objects.filter(
            status=Invoice.Status.ISSUED,
            due_date__lt=today
        ).exclude(invoice_type__in=['CASH', 'COD']).order_by('due_date', '-total_amount')
        
        # Filtering logic
        date_from = request.GET.get('date_from')
        if date_from:
            overdue_qs = overdue_qs.filter(due_date__gte=date_from)
            
        date_to = request.GET.get('date_to')
        if date_to:
            overdue_qs = overdue_qs.filter(due_date__lte=date_to)
            
        month = request.GET.get('month')
        if month:
            try:
                year_str, month_str = month.split('-')
                overdue_qs = overdue_qs.filter(due_date__year=int(year_str), due_date__month=int(month_str))
            except ValueError:
                pass
            
        q = request.GET.get('q')
        if q:
            overdue_qs = overdue_qs.filter(
                Q(invoice_number__icontains=q) |
                Q(customer__customer_name__icontains=q)
            )

        salesperson_id = request.GET.get('salesperson')
        if salesperson_id:
            overdue_qs = overdue_qs.filter(salesperson_id=salesperson_id)

        # Calculate remaining balances
        invoices = []
        for inv in overdue_qs:
            total_paid = sum(p.amount for p in inv.payments.all())
            balance = inv.total_amount - total_paid
            if balance > 0:
                invoices.append({
                    'id': inv.id,
                    'invoice_number': inv.invoice_number,
                    'customer': inv.customer,
                    'salesperson': inv.salesperson,
                    'due_date': inv.due_date,
                    'total_amount': inv.total_amount,
                    'total_paid': total_paid,
                    'balance': balance,
                    'days_overdue': (today - inv.due_date).days
                })
                
        # Optional: Pagination could be added here if needed, but standard python lists might be small enough for overdue invoices.
        
        from users.models import User
        sales_officers = User.objects.filter(role__name='Sales Officer', is_active=True).distinct()
                
        context = {
            'invoices': invoices,
            'payment_methods': Payment.PaymentMethod.choices,
            'sales_officers': sales_officers
        }
        
        # Provide Saved Filters
        try:
            from users.models import SavedFilter
            context['saved_filters'] = SavedFilter.objects.filter(user=request.user, model_name='OverdueInvoices')
        except ImportError:
            context['saved_filters'] = []
            
        return render(request, self.template_name, context)

class RecordPaymentView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'

    def post(self, request):
        try:
            data = json.loads(request.body)
            invoice_id = data.get('invoice_id')
            amount_str = data.get('amount')
            payment_date_str = data.get('payment_date')
            payment_method = data.get('payment_method')
            reference = data.get('reference', '')
            notes = data.get('notes', '')

            invoice = get_object_or_404(Invoice, id=invoice_id)
            amount = float(amount_str)
            payment_date = datetime.strptime(payment_date_str, '%Y-%m-%d').date()

            with transaction.atomic():
                Payment.objects.create(
                    invoice=invoice,
                    amount=amount,
                    payment_date=payment_date,
                    payment_method=payment_method,
                    reference_number=reference,
                    notes=notes,
                    recorded_by=request.user
                )

            return JsonResponse({'status': 'ok', 'message': 'Payment recorded successfully.'})

        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
class AgedReceivablesView(LoginRequiredMixin, PermissionRequiredMixin, View):
    permission_required = 'finance.manage_finance'
    template_name = 'finance/aged_receivables.html'

    def get(self, request):
        today = timezone.now().date()
        
        qs = Invoice.objects.filter(
            status=Invoice.Status.ISSUED
        ).exclude(invoice_type__in=['CASH', 'COD']).select_related('customer', 'salesperson').prefetch_related('payments')
        
        customers_data = {}
        
        for inv in qs:
            total_paid = sum(p.amount for p in inv.payments.all())
            balance = inv.total_amount - total_paid
            
            if balance <= 0:
                continue
                
            customer_id = inv.customer.id
            if customer_id not in customers_data:
                customers_data[customer_id] = {
                    'customer': inv.customer,
                    'invoices': [],
                    'not_due': 0,
                    '1_30': 0,
                    '31_45': 0,
                    '46_60': 0,
                    '61_90': 0,
                    '91_120': 0,
                    'older': 0,
                    'total': 0
                }
                
            days_overdue = (today - inv.due_date).days
            
            inv_data = {
                'id': inv.id,
                'invoice_number': inv.invoice_number,
                'salesperson': inv.salesperson,
                'due_date': inv.due_date,
                'total_amount': inv.total_amount,
                'balance': balance,
                'days_overdue': days_overdue
            }
            
            if days_overdue <= 0:
                customers_data[customer_id]['not_due'] += balance
                inv_data['bucket'] = 'not_due'
            elif 1 <= days_overdue <= 30:
                customers_data[customer_id]['1_30'] += balance
                inv_data['bucket'] = '1_30'
            elif 31 <= days_overdue <= 45:
                customers_data[customer_id]['31_45'] += balance
                inv_data['bucket'] = '31_45'
            elif 46 <= days_overdue <= 60:
                customers_data[customer_id]['46_60'] += balance
                inv_data['bucket'] = '46_60'
            elif 61 <= days_overdue <= 90:
                customers_data[customer_id]['61_90'] += balance
                inv_data['bucket'] = '61_90'
            elif 91 <= days_overdue <= 120:
                customers_data[customer_id]['91_120'] += balance
                inv_data['bucket'] = '91_120'
            else:
                customers_data[customer_id]['older'] += balance
                inv_data['bucket'] = 'older'
                
            customers_data[customer_id]['total'] += balance
            customers_data[customer_id]['invoices'].append(inv_data)
            
        customers_list = list(customers_data.values())
        customers_list.sort(key=lambda x: x['total'], reverse=True)
        
        grand_totals = {
            'not_due': sum(c['not_due'] for c in customers_list),
            '1_30': sum(c['1_30'] for c in customers_list),
            '31_45': sum(c['31_45'] for c in customers_list),
            '46_60': sum(c['46_60'] for c in customers_list),
            '61_90': sum(c['61_90'] for c in customers_list),
            '91_120': sum(c['91_120'] for c in customers_list),
            'older': sum(c['older'] for c in customers_list),
            'total': sum(c['total'] for c in customers_list),
        }
        
        context = {
            'customers_data': customers_list,
            'grand_totals': grand_totals,
            'today': today
        }
        
        return render(request, self.template_name, context)
