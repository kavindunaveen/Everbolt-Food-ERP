from sales.models import Invoice, CreditNote
import traceback
try:
    inv = Invoice.objects.filter(invoice_number='26AUG_EBFR_01490').first()
    if inv:
        print("Invoice:", inv.invoice_number, "Total Amount:", inv.total_amount)
        for cn in inv.credit_notes.all():
            print("  CreditNote:", cn.credit_note_number, "Status:", cn.status, "Total Credit:", cn.total_credit_with_tax)
            for item in cn.items.all():
                print("    Item:", item.product.name, "Qty:", item.quantity, "CreditAmount:", item.credit_amount)
    else:
        print("Invoice not found")
except Exception as e:
    traceback.print_exc()
