import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()

from sales.models import Return, ReturnItem
from django.forms import inlineformset_factory

initial_data = [{'quantity': 2, 'unit_price': 100}, {'quantity': 5, 'unit_price': 50}]
FS1 = inlineformset_factory(Return, ReturnItem, fields=('quantity', 'unit_price'), extra=2)
fs1 = FS1(initial=initial_data)

html = fs1.as_p()
print("HTML length:", len(html))
print(html)
