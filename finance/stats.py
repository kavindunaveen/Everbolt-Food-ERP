from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from decimal import Decimal
from sales.models import Invoice

def get_invoice_stats(today):
    total_invoices_all = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED, Invoice.Status.APPROVAL_PENDING]).count()
    total_invoices_month = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED, Invoice.Status.APPROVAL_PENDING]).filter(creation_date__year=today.year, creation_date__month=today.month).count()
    
    valid_statuses = [Invoice.Status.ISSUED, Invoice.Status.PAID, Invoice.Status.EDIT_PENDING, Invoice.Status.CANCEL_PENDING]
    issued_qs = Invoice.objects.filter(status__in=valid_statuses).annotate(
        total_paid_agg=Coalesce(Sum('payments__amount'), Decimal('0.00'))
    ).prefetch_related('credit_notes', 'credit_notes__items')
    
    completed_count = 0
    pending_count = 0
    partial_count = 0
    
    for inv in issued_qs:
        total_credits = sum((c.total_credit_with_tax for c in inv.credit_notes.all() if c.status == 'APPROVED'), Decimal('0.00'))
        balance_due = inv.total_amount - inv.total_paid_agg - total_credits
        if balance_due < Decimal('0.01'):
            completed_count += 1
        elif inv.total_paid_agg < Decimal('0.01'):
            pending_count += 1
        else:
            partial_count += 1
    
    return {
        'total_invoices_all': total_invoices_all,
        'total_invoices_month': total_invoices_month,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'partial_count': partial_count,
    }
