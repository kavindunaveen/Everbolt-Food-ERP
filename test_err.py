import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from inventory.models import Product
from purchases.models import PurchaseOrderItem
p = Product.objects.filter(stock_unit='pack').first()
poi = PurchaseOrderItem(qty=1.5, product=p)
try:
    poi.clean()
except Exception as e:
    print('STRING:', repr(str(e)))
