import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()

from sales.models import Invoice, Quotation
from django.db import transaction

def fix_sales_officers():
    print("Starting Sales Officer synchronization for DRAFT records...")
    
    with transaction.atomic():
        # 1. Update Invoices (DRAFT, APPROVAL_PENDING, EDIT_PENDING)
        target_statuses = ['DRAFT', 'APPROVAL_PENDING', 'EDIT_PENDING']
        active_invoices = Invoice.objects.filter(status__in=target_statuses).select_related('customer', 'salesperson')
        updated_inv_count = 0
        for inv in active_invoices:
            correct_officer = inv.customer.assigned_sales_officer
            if correct_officer and inv.salesperson != correct_officer:
                old_officer = inv.salesperson.username if inv.salesperson else "None"
                inv.salesperson = correct_officer
                inv.save(update_fields=['salesperson'])
                print(f"Updated Invoice {inv.invoice_number} ({inv.status}): {old_officer} -> {correct_officer.username}")
                updated_inv_count += 1
        
        # 2. Update Quotations (DRAFT, SENT)
        q_target_statuses = ['DRAFT', 'SENT']
        active_quotations = Quotation.objects.filter(status__in=q_target_statuses).select_related('customer', 'salesperson')
        updated_q_count = 0
        for q in active_quotations:
            correct_officer = q.customer.assigned_sales_officer
            if correct_officer and q.salesperson != correct_officer:
                old_officer = q.salesperson.username if q.salesperson else "None"
                q.salesperson = correct_officer
                q.save(update_fields=['salesperson'])
                print(f"Updated Quotation {q.quotation_number} ({q.status}): {old_officer} -> {correct_officer.username}")
                updated_q_count += 1
                
    print(f"\nSummary:")
    print(f"Total DRAFT Invoices updated: {updated_inv_count}")
    print(f"Total DRAFT Quotations updated: {updated_q_count}")
    print("Synchronization complete.")

if __name__ == "__main__":
    fix_sales_officers()
