import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from sales.models import Invoice

qs = Invoice.objects.filter(salesperson__username='admin', status='ISSUED')
for inv in qs:
    print(f"Invoice {inv.id}: tax_amount={inv.tax_amount}, total={inv.total_amount}")
