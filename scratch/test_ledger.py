from sales.models import Return, CreditNote
from inventory.models import StockLedger, Product

try:
    p = Product.objects.get(name__icontains='Sugar sachet - White - 5g')
    print('Sugar stock:', p.current_stock)
    print('Sugar ledger:', [(l.tx_type, l.qty_in, l.qty_out) for l in StockLedger.objects.filter(product=p, reference_type__contains='RTN')])
except Exception as e:
    print("Sugar error:", e)

try:
    p2 = Product.objects.get(name__icontains='Creamer Sachet')
    print('Creamer stock:', p2.current_stock)
    print('Creamer ledger:', [(l.tx_type, l.qty_in, l.qty_out) for l in StockLedger.objects.filter(product=p2, reference_type__contains='RTN')])
except Exception as e:
    print("Creamer error:", e)
