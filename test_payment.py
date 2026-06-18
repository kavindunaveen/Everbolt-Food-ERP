import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from finance.models import Payment
from sales.models import Invoice

print(float(""))
