from sales.models import Invoice
updated = 0
skipped = 0
for i in Invoice.objects.filter(salesperson__username='binudi'):
    off = i.customer.assigned_sales_officer
    if off:
        Invoice.objects.filter(pk=i.pk).update(salesperson=off)
        updated += 1
    else:
        skipped += 1
print(f"DONE. Updated: {updated}, Skipped: {skipped}")
