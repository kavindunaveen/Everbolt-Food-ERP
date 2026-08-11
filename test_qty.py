import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from inventory.models import Product
from purchases.models import PurchaseOrderItem
p = Product.objects.filter(stock_unit='pack').first()
poi = PurchaseOrderItem(qty='13000', product=p)
try:
    print(type(poi.qty))
    print(poi.qty % 1 != 0)
except Exception as e:
    print('ERROR:', type(e), e)
