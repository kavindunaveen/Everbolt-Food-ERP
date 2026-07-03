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
    )
    
    completed_count = issued_qs.filter(total_paid_agg__gte=F('total_amount') - Decimal('0.009')).count()
    pending_count = issued_qs.filter(total_paid_agg__lt=Decimal('0.01')).count()
    partial_count = issued_qs.filter(total_paid_agg__gte=Decimal('0.01'), total_paid_agg__lt=F('total_amount') - Decimal('0.009')).count()
    
    return {
        'total_invoices_all': total_invoices_all,
        'total_invoices_month': total_invoices_month,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'partial_count': partial_count,
    }
