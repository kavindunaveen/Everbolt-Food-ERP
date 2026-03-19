from django.db import transaction
from inventory.models import StockLedger, Product

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
        invoice.status = 'ISSUED'
        invoice.save(update_fields=['status'])
        
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

def cancel_invoice(invoice, user):
    """
    Cancels an ISSUED invoice and restores stock.
    """
    if invoice.status != 'ISSUED':
        raise ValueError("Only ISSUED invoices can be cancelled.")
        
    with transaction.atomic():
        invoice.status = 'CANCELLED'
        invoice.save(update_fields=['status'])
        
        ledgers = []
        for item in invoice.items.all():
            qty = item.quantity
            if qty > 0:
                ledgers.append(StockLedger(
                    product=item.product,
                    tx_type=StockLedger.TransactionTypes.SALES_RET, # Restoration from cancel is basically a return
                    qty_in=qty,
                    qty_out=0,
                    reference_type='INV-CANCEL',
                    reference_id=invoice.id,
                    reference_number=invoice.invoice_number,
                    remarks=f"Stock Restoration (Cancel {invoice.invoice_number})",
                    user=user
                ))
                
                prod_obj = Product.objects.select_for_update().get(id=item.product.id)
                prod_obj.current_stock += qty
                prod_obj.save(update_fields=['current_stock'])
                
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
