from django.db import transaction
from .models import GRN
from inventory.models import StockLedger, Product

def confirm_grn(grn, user):
    """
    Confirms a GRN, creating StockLedger entries for each item,
    and changing the GRN status to CONFIRMED.
    """
    if grn.status != GRN.StatusChoices.DRAFT:
        raise ValueError("Only DRAFT GRNs can be confirmed.")
        
    with transaction.atomic():
        grn.status = GRN.StatusChoices.CONFIRMED
        grn.save(update_fields=['status', 'updated_at'])
        
        ledgers = []
        for item in grn.items.all():
            ledgers.append(StockLedger(
                product=item.product,
                tx_type=StockLedger.TransactionTypes.GRN,
                qty_in=item.qty,
                qty_out=0,
                reference_type='GRN',
                reference_id=grn.id,
                reference_number=grn.grn_number,
                remarks=f"Received via {grn.supplier}",
                user=user
            ))
            
            product = Product.objects.select_for_update().get(id=item.product.id)
            product.current_stock += item.qty
            product.save(update_fields=['current_stock'])
            
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)

def cancel_grn(grn, user):
    """
    Cancels a CONFIRMED GRN by creating reversing StockLedger entries.
    """
    if grn.status != GRN.StatusChoices.CONFIRMED:
        raise ValueError("Only CONFIRMED GRNs can be cancelled.")
        
    with transaction.atomic():
        grn.status = GRN.StatusChoices.CANCELLED
        grn.save(update_fields=['status', 'updated_at'])
        
        ledgers = []
        for item in grn.items.all():
            ledgers.append(StockLedger(
                product=item.product,
                tx_type=StockLedger.TransactionTypes.GRN,
                qty_in=0,
                qty_out=item.qty, # Reverse the IN by putting it in OUT
                reference_type='GRN-CANCEL',
                reference_id=grn.id,
                reference_number=grn.grn_number,
                remarks=f"Cancelled GRN",
                user=user
            ))
            
            product = Product.objects.select_for_update().get(id=item.product.id)
            product.current_stock -= item.qty
            product.save(update_fields=['current_stock'])
            
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
