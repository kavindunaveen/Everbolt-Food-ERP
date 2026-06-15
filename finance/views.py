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
                
        context = {
            'invoices': invoices,
            'payment_methods': Payment.PaymentMethod.choices
        }
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
