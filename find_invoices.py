import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from finance.models import Payment
from sales.models import Invoice
from django.utils import timezone
from datetime import timedelta

recent_payments = Payment.objects.filter(created_at__gte=timezone.now() - timedelta(hours=24)).order_by('-created_at')
for p in recent_payments:
    print(f"Payment ID: {p.id}, Invoice: {p.invoice.invoice_number}, Amount: {p.amount}, Date: {p.created_at}")

