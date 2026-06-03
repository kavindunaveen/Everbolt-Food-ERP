import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from sales.models import Invoice
from django.db.models import F

# Backfill subtotal_amount for invoices where it is 0 but total_amount > 0
invoices_to_fix = Invoice.objects.filter(subtotal_amount=0, total_amount__gt=0)
count = invoices_to_fix.count()
print(f"Found {count} invoices to backfill.")

for inv in invoices_to_fix:
    inv.subtotal_amount = inv.total_amount - inv.tax_amount
    inv.save(update_fields=['subtotal_amount'])

print("Done.")

