import os
import django
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from sales.models import Return, ReturnItem
from django.forms import inlineformset_factory

initial_data = [{'quantity': 2, 'unit_price': 100}]

FS1 = inlineformset_factory(Return, ReturnItem, fields=('quantity', 'unit_price'), extra=0)
fs1 = FS1(initial=initial_data)
print(f"extra=0 -> {len(fs1.forms)} forms")

FS2 = inlineformset_factory(Return, ReturnItem, fields=('quantity', 'unit_price'), extra=1)
fs2 = FS2(initial=initial_data)
print(f"extra=1 -> {len(fs2.forms)} forms")
