import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from django import forms
from purchases.models import PurchaseOrder
class F(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = '__all__'
f = F()
print(f.as_p())
