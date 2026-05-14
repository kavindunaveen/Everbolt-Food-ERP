import os
import sys
import django
from decimal import Decimal

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()

from sales.models import Invoice, Quotation

def backfill_subtotals():
    # Backfill Invoices
    invoices = Invoice.objects.all()
    for inv in invoices:
        # Approximate subtotal from existing data if items aren't easily summed
        # But we can try to sum items for better accuracy
        items_total = sum((item.quantity * item.unit_price) for item in inv.items.all())
        line_discount = sum(item.get_discount_amount for item in inv.items.all())
        subtotal = items_total - line_discount
        
        custom_val = inv.custom_discount_value or Decimal('0.00')
        if inv.custom_discount_type == 'PERCENT':
            global_discount = subtotal * (custom_val / Decimal('100.0'))
        else:
            global_discount = custom_val
            
        final_subtotal = subtotal - global_discount
        if final_subtotal < 0: final_subtotal = 0
        
        inv.subtotal_amount = final_subtotal
        inv.save()
        print(f"Updated Invoice {inv.invoice_number}: Subtotal = {final_subtotal}")

    # Backfill Quotations
    quotations = Quotation.objects.all()
    for q in quotations:
        items_total = sum((item.quantity * item.unit_price) for item in q.items.all())
        line_discount = sum(item.get_discount_amount for item in q.items.all())
        subtotal = items_total - line_discount
        
        custom_val = q.custom_discount_value or Decimal('0.00')
        if q.custom_discount_type == 'PERCENT':
            global_discount = subtotal * (custom_val / Decimal('100.0'))
        else:
            global_discount = custom_val
            
        final_subtotal = subtotal - global_discount
        if final_subtotal < 0: final_subtotal = 0
        
        q.subtotal_amount = final_subtotal
        q.save()
        print(f"Updated Quotation {q.quotation_number}: Subtotal = {final_subtotal}")

if __name__ == "__main__":
    backfill_subtotals()
