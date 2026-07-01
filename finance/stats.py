from django.db.models import Sum, F
from django.db.models.functions import Coalesce
from decimal import Decimal
from sales.models import Invoice

def get_invoice_stats(today):
    total_invoices_all = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED, Invoice.Status.CANCEL_PENDING]).count()
    total_invoices_month = Invoice.objects.exclude(status__in=[Invoice.Status.DRAFT, Invoice.Status.CANCELLED, Invoice.Status.CANCEL_PENDING]).filter(creation_date__year=today.year, creation_date__month=today.month).count()
    completed_count = Invoice.objects.filter(status=Invoice.Status.PAID).count()
    
    issued_qs = Invoice.objects.filter(status=Invoice.Status.ISSUED).annotate(
        total_paid_agg=Coalesce(Sum('payments__amount'), Decimal('0.00'))
    )
    pending_count = issued_qs.filter(total_paid_agg=0).count()
    partial_count = issued_qs.filter(total_paid_agg__gt=0).count()
    
    return {
        'total_invoices_all': total_invoices_all,
        'total_invoices_month': total_invoices_month,
        'completed_count': completed_count,
        'pending_count': pending_count,
        'partial_count': partial_count,
    }
