import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from sales.models import Invoice
from django.db.models import Count

invoices = Invoice.objects.values('salesperson__username').annotate(count=Count('id'))
print("Invoices per salesperson:", list(invoices))
