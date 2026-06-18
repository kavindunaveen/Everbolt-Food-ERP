import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from sales.models import Invoice

qs = Invoice.objects.filter(salesperson__username='admin')
print("Admin invoices statuses:")
for inv in qs:
    print(f"Invoice {inv.id}: status={inv.status}, creation_date={inv.creation_date}, total={inv.total_amount}")
