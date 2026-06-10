from django.db import transaction
from django.db.models import Q
from django.core.mail import send_mail
from django.conf import settings
from users.models import User
from inventory.models import StockLedger, Product, StockReserve
from django.utils import timezone
from datetime import timedelta
from .models import SalesAuditLog, Return, CreditNote

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
            
        # Re-evaluate stock levels since reserves affect available_stock
        from inventory.services import check_and_notify_stock_levels
        for item in invoice.items.all():
            check_and_notify_stock_levels(item.product)

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
    - Changes invoice status to ISSUED.
    - Stock deduction is now deferred to Delivery Note creation.
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
            notes="Invoice finalized. Stock will be deducted upon Delivery Note creation."
        )
            
        update_stock_reserves(invoice)

def deduct_dn_stock(dn, user):
    """
    Deducts stock for a Delivery Note if the associated invoice hasn't already.
    """
    invoice = dn.invoice
    if invoice.stock_deducted:
        return
        
    ledgers = []
    with transaction.atomic():
        for item in dn.items.all():
            qty = item.quantity
            if qty > 0 and item.product.track_stock:
                prod_obj = Product.objects.select_for_update().get(id=item.product.id)
                if not prod_obj.allow_negative_stock and prod_obj.current_stock < qty:
                    raise ValueError(f"Insufficient stock for {prod_obj.name}. Available: {prod_obj.current_stock}")
                
                ledgers.append(StockLedger(
                    product=item.product,
                    tx_type=StockLedger.TransactionTypes.SALES_ISS,
                    qty_in=0,
                    qty_out=qty,
                    reference_type='DN',
                    reference_id=dn.id,
                    reference_number=dn.dn_number,
                    remarks=f"Delivery Note Issue {dn.dn_number} for Invoice {invoice.invoice_number}",
                    user=user
                ))
                
                prod_obj.current_stock -= qty
                prod_obj.save(update_fields=['current_stock'])
        
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
            
        from inventory.services import check_and_notify_stock_levels
        for item in dn.items.all():
            if item.product.track_stock:
                check_and_notify_stock_levels(item.product)
            
        invoice.stock_deducted = True
        invoice.save(update_fields=['stock_deducted'])

def restore_dn_stock(dn, user, remark_prefix="Delivery Failed"):
    """
    Restores stock if a Delivery Note fails.
    """
    invoice = dn.invoice
    if not invoice.stock_deducted:
        return
        
    ledgers = []
    with transaction.atomic():
        for item in dn.items.all():
            qty = item.quantity
            if qty > 0 and item.product.track_stock:
                ledgers.append(StockLedger(
                    product=item.product,
                    tx_type=StockLedger.TransactionTypes.SALES_RET,
                    qty_in=qty,
                    qty_out=0,
                    reference_type='DN-RESTORE',
                    reference_id=dn.id,
                    reference_number=dn.dn_number,
                    remarks=f"{remark_prefix} ({dn.dn_number})",
                    user=user
                ))
                
                prod_obj = Product.objects.select_for_update().get(id=item.product.id)
                prod_obj.current_stock += qty
                prod_obj.save(update_fields=['current_stock'])
                
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
            
        from inventory.services import check_and_notify_stock_levels
        for item in dn.items.all():
            if item.product.track_stock:
                check_and_notify_stock_levels(item.product)
            
        invoice.stock_deducted = False
        invoice.save(update_fields=['stock_deducted'])

def restore_stock(invoice, user, remark_prefix="Stock Restoration"):
    """
    Internal helper to restore stock for all items in an invoice.
    Only restores stock if it was actually deducted (stock_deducted=True).
    """
    if not invoice.stock_deducted:
        return
        
    ledgers = []
    for item in invoice.items.all():
        qty = item.quantity
        if qty > 0 and item.product.track_stock:
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
        
    from inventory.services import check_and_notify_stock_levels
    for item in invoice.items.all():
        if item.quantity > 0 and item.product.track_stock:
            check_and_notify_stock_levels(item.product)
        
    invoice.stock_deducted = False
    invoice.save(update_fields=['stock_deducted'])
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
            Q(role__name='Administrator') | 
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


def process_return(return_obj, user):
    """
    Processes a customer return:
      1. Restores stock to inventory via StockLedger (SALES_RET) for all items.
      2. Updates Product.current_stock cache.
      3. Marks Return.stock_updated = True.
      4. Generates a CreditNote and CreditNoteItems automatically.
      5. Marks Return.credit_note_issued = True.
    """
    if return_obj.stock_updated:
        raise ValueError(f"Return {return_obj.return_number} has already been processed.")

    from .models import CreditNoteItem

    with transaction.atomic():
        # 1. Create Credit Note header
        credit_note = CreditNote.objects.create(
            return_record=return_obj,
            original_invoice=return_obj.original_invoice,
            customer=return_obj.original_invoice.customer,
            issued_by=user,
            notes=f"Auto-generated for return {return_obj.return_number}."
        )

        total_credit_value = 0
        items_summary = []

        # 2. Loop through ReturnItems
        for return_item in return_obj.items.all():
            product = Product.objects.select_for_update().get(pk=return_item.product.pk)
            qty = return_item.quantity
            credit_amount = return_item.credit_value
            total_credit_value += credit_amount
            items_summary.append(f"{qty}x {product.name}")

            # Handle Stock Ledger & Cache if product tracks stock
            if product.track_stock:
                # Write stock ledger entry for the return (inward)
                StockLedger.objects.create(
                    product=product,
                    tx_type=StockLedger.TransactionTypes.SALES_RET,
                    qty_in=qty,
                    qty_out=0,
                    reference_type='RTN',
                    reference_id=return_obj.pk,
                    reference_number=return_obj.return_number,
                    remarks=(
                        f"Return {return_obj.return_number} | "
                        f"Inv: {return_obj.original_invoice.invoice_number} | "
                        f"Cond: {return_item.get_condition_display()}"
                    ),
                    user=user,
                )

                if return_item.condition == 'SELLABLE':
                    # Update product stock cache
                    product.current_stock += qty
                    if product.current_stock > 0:
                        product.status = True
                    product.save(update_fields=['current_stock', 'status'])
                else:
                    # If DAMAGED, the stock came back but shouldn't be added to sellable stock.
                    # We write an immediate OUT adjustment so the ledger stays balanced with current_stock.
                    StockLedger.objects.create(
                        product=product,
                        tx_type=StockLedger.TransactionTypes.ADJ_NEG,
                        qty_in=0,
                        qty_out=qty,
                        reference_type='RTN_DMG',
                        reference_id=return_obj.pk,
                        reference_number=f"{return_obj.return_number}-DMG",
                        remarks=f"Auto write-off for damaged return {return_obj.return_number}",
                        user=user,
                    )
                
                from inventory.services import check_and_notify_stock_levels
                check_and_notify_stock_levels(product)

            # Generate Credit Note Item
            CreditNoteItem.objects.create(
                credit_note=credit_note,
                product=product,
                quantity=qty,
                unit_price=return_item.unit_price,
                credit_amount=credit_amount
            )

        # 3. Mark return as processed
        return_obj.stock_updated = True
        return_obj.credit_note_issued = True
        return_obj.save(update_fields=['stock_updated', 'credit_note_issued'])

        items_str = ", ".join(items_summary)
        
        # 4. Audit log
        log_sales_event(
            obj=return_obj.original_invoice,
            user=user,
            action="Customer Return Processed",
            new_value=return_obj.return_number,
            notes=(
                f"Returned items: {items_str}. "
                f"Stock restored. Credit Note {credit_note.credit_note_number} issued. "
                f"Total Credit Value: Rs {total_credit_value}."
            ),
        )

    return credit_note
