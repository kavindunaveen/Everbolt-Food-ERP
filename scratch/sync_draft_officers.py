import os
import sys
import django

sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()

from sales.models import Invoice, Quotation

def sync_all_drafts():
    # Sync Invoices
    invoices = Invoice.objects.filter(status__in=['DRAFT', 'APPROVAL_PENDING', 'EDIT_PENDING'])
    for inv in invoices:
        correct_officer = inv.customer.assigned_sales_officer
        if inv.salesperson != correct_officer:
            print(f"Syncing Invoice {inv.invoice_number}: {inv.salesperson} -> {correct_officer}")
            inv.salesperson = correct_officer
            inv.save()

    # Sync Quotations
    quotations = Quotation.objects.filter(status__in=['DRAFT', 'SENT'])
    for q in quotations:
        correct_officer = q.customer.assigned_sales_officer
        if q.salesperson != correct_officer:
            print(f"Syncing Quotation {q.quotation_number}: {q.salesperson} -> {correct_officer}")
            q.salesperson = correct_officer
            q.save()

if __name__ == "__main__":
    sync_all_drafts()
