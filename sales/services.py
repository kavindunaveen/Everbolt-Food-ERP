from django.db import transaction
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from users.models import User
from inventory.models import StockLedger, Product, StockReserve
from django.utils import timezone
from datetime import timedelta
from .models import SalesAuditLog

def update_stock_reserves(invoice):
    """
    Updates or creates stock reserves for all items in a DRAFT invoice.
    Reserves are valid for 15 minutes from the last update.
    """
    if invoice.status != 'DRAFT':
        # Remove any existing reserves if not draft
        StockReserve.objects.filter(reference_type='INV', reference_id=invoice.id).delete()
        return

    with transaction.atomic():
        # Clear existing for this invoice to recalculate
        StockReserve.objects.filter(reference_type='INV', reference_id=invoice.id).delete()
        
        expiry = timezone.now() + timedelta(minutes=15)
        reserves = []
        for item in invoice.items.all():
            reserves.append(StockReserve(
                product=item.product,
                quantity=item.quantity,
                reference_type='INV',
                reference_id=invoice.id,
                expiry_time=expiry
            ))
        
        if reserves:
            StockReserve.objects.bulk_create(reserves)

def log_sales_event(obj, user, action, old_value=None, new_value=None, notes=None):
    """
    Creates an audit log entry for a sales-related object.
    """
    SalesAuditLog.objects.create(
        content_object=obj,
        user=user,
        action=action,
        old_value=str(old_value) if old_value else None,
        new_value=str(new_value) if new_value else None,
        notes=notes
    )

def issue_invoice(invoice, user):
    """
    Confirms/Issues a Sales Invoice.
    - Creates StockLedger entries (SALES_ISS) for each item.
    - Updates Product current_stock cache.
    - Changes invoice status to ISSUED.
    """
    if invoice.status != 'DRAFT':
        raise ValueError("Only DRAFT invoices can be issued.")
        
    with transaction.atomic():
        old_status = invoice.get_status_display()
        invoice.status = 'ISSUED'
        invoice.save(update_fields=['status'])
        
        log_sales_event(
            obj=invoice,
            user=user,
            action="Invoice Issued",
            old_value=old_status,
            new_value=invoice.get_status_display(),
            notes="Stock deducted and invoice finalized."
        )
        
        ledgers = []
        for item in invoice.items.all():
            qty = item.quantity
            if qty > 0:
                # Check for negative stock
                prod_obj = Product.objects.select_for_update().get(id=item.product.id)
                if not prod_obj.allow_negative_stock and prod_obj.current_stock < qty:
                    raise ValueError(f"Insufficient stock for {prod_obj.name}. Available: {prod_obj.current_stock}")
                
                ledgers.append(StockLedger(
                    product=item.product,
                    tx_type=StockLedger.TransactionTypes.SALES_ISS,
                    qty_in=0,
                    qty_out=qty,
                    reference_type='INV',
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    remarks=f"Sales Issue for {invoice.invoice_number} to {invoice.customer.customer_name}",
                    user=user
                ))
                
                prod_obj.current_stock -= qty
                prod_obj.save(update_fields=['current_stock'])
        
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
            
        update_stock_reserves(invoice)

def restore_stock(invoice, user, remark_prefix="Stock Restoration"):
    """
    Internal helper to restore stock for all items in an invoice.
    """
    ledgers = []
    for item in invoice.items.all():
        qty = item.quantity
        if qty > 0:
            ledgers.append(StockLedger(
                product=item.product,
                tx_type=StockLedger.TransactionTypes.SALES_RET,
                qty_in=qty,
                qty_out=0,
                reference_type='INV-RESTORE',
                reference_id=invoice.id,
                reference_number=invoice.invoice_number,
                remarks=f"{remark_prefix} ({invoice.invoice_number})",
                user=user
            ))
            
            prod_obj = Product.objects.select_for_update().get(id=item.product.id)
            prod_obj.current_stock += qty
            prod_obj.save(update_fields=['current_stock'])
            
    if ledgers:
        StockLedger.objects.bulk_create(ledgers)
    update_stock_reserves(invoice)

def cancel_invoice(invoice, user):
    """
    Cancels an ISSUED invoice and restores stock.
    """
    if invoice.status not in ['ISSUED', 'CANCEL_PENDING']:
        raise ValueError("Only ISSUED or CANCEL_PENDING invoices can be cancelled.")
        
    with transaction.atomic():
        old_status = invoice.get_status_display()
        invoice.status = 'CANCELLED'
        invoice.save(update_fields=['status'])
        
        log_sales_event(
            obj=invoice,
            user=user,
            action="Invoice Cancelled",
            old_value=old_status,
            new_value=invoice.get_status_display(),
            notes="Invoice cancelled and stock restored."
        )
        
        restore_stock(invoice, user, "Invoice Cancelled")

from users.models import Notification

def send_invoice_approval_email(invoice, request):
    """
    Creates an in-app notification and sends an email to the designated approver.
    """
    if invoice.designated_approver:
        approvers = [invoice.designated_approver]
    else:
        approvers = User.objects.filter(
            Q(is_superuser=True) | 
            Q(role='ADMIN') | 
            Q(user_permissions__codename='approve_invoice')
        ).filter(is_active=True).distinct()
    
    # Create In-App Notification for all designated approvers
    for manager in approvers:
        Notification.objects.create(
            recipient=manager,
            title=f"Approval Required: {invoice.invoice_number}",
            message=f"Invoice for {invoice.customer.customer_name} (Rs {invoice.total_amount}). Needs approval because customer is {invoice.customer.get_customer_status_display()}.",
            link="/sales/invoices/"
        )
    
    recipient_list = [user.email for user in approvers if user.email]
    
    if not recipient_list:
        return
        
    subject = f"Invoice Approval Required: {invoice.invoice_number}"
    
    url = request.build_absolute_uri(f"/sales/")
    
    message = (
        f"Hello,\n\n"
        f"A new invoice ({invoice.invoice_number}) has been drafted by {invoice.salesperson.get_full_name() or invoice.salesperson.username} "
        f"for customer '{invoice.customer.customer_name}', but requires approval because the customer is marked as {invoice.customer.get_customer_status_display()}.\n\n"
        f"Invoice Total: Rs {invoice.total_amount}\n\n"
        f"Please log in to the system to approve or reject this invoice:\n{url}\n\n"
        f"Thank you,\nEverbolt ERP System"
    )
    
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@everbolt.com',
            recipient_list=recipient_list,
            fail_silently=True,
        )
    except Exception as e:
        print(f"Failed to send email notification: {str(e)}")
