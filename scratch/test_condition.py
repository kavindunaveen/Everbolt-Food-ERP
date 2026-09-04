from sales.models import Return, CreditNote
try:
    r = Return.objects.get(return_number='RTN-0010')
    print("Return:", r.return_number, "stock_updated:", r.stock_updated)
    for i in r.items.all():
        print("  ReturnItem:", i.product.name, "Reason:", i.reason, "Condition:", i.condition)
    
    cn = CreditNote.objects.get(credit_note_number='CN-0017')
    print("CreditNote:", cn.credit_note_number, "Status:", cn.status)
    for i in cn.items.all():
        print("  CN Item:", i.product.name)
except Exception as e:
    import traceback
    traceback.print_exc()
