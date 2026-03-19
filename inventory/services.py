from django.db import transaction
from .models import StockAdjustment, StockLedger, Product

def confirm_stock_adjustment(adjustment, user):
    """
    Confirms a Stock Adjustment, creating StockLedger entry,
    and updating the Product's current_stock cache.
    """
    if adjustment.status != StockAdjustment.StatusChoices.DRAFT:
        raise ValueError("Only DRAFT adjustments can be confirmed.")
        
    with transaction.atomic():
        adjustment.status = StockAdjustment.StatusChoices.CONFIRMED
        adjustment.save(update_fields=['status'])
        
        qty_in = 0
        qty_out = 0
        
        if adjustment.adjustment_type == StockAdjustment.AdjustmentTypes.POSITIVE:
            qty_in = adjustment.quantity
        else:
            qty_out = adjustment.quantity
            
        # Create Ledger Entry
        StockLedger.objects.create(
            product=adjustment.product,
            tx_type=(StockLedger.TransactionTypes.ADJ_POS 
                     if adjustment.adjustment_type == StockAdjustment.AdjustmentTypes.POSITIVE 
                     else StockLedger.TransactionTypes.ADJ_NEG),
            qty_in=qty_in,
            qty_out=qty_out,
            reference_type='ADJ',
            reference_id=adjustment.id,
            reference_number=adjustment.adjustment_number,
            remarks=adjustment.reason,
            user=user
        )
        
        # Update Product Cache
        product = Product.objects.select_for_update().get(id=adjustment.product.id)
        product.current_stock += (qty_in - qty_out)
        product.save(update_fields=['current_stock'])

def cancel_stock_adjustment(adjustment, user):
    """
    Cancels a CONFIRMED Stock Adjustment by creating a reversing StockLedger entry.
    """
    if adjustment.status != StockAdjustment.StatusChoices.CONFIRMED:
        raise ValueError("Only CONFIRMED adjustments can be cancelled.")
        
    with transaction.atomic():
        adjustment.status = StockAdjustment.StatusChoices.CANCELLED
        adjustment.save(update_fields=['status'])
        
        # Original adjustment values
        orig_qty_in = adjustment.quantity if adjustment.adjustment_type == StockAdjustment.AdjustmentTypes.POSITIVE else 0
        orig_qty_out = adjustment.quantity if adjustment.adjustment_type == StockAdjustment.AdjustmentTypes.NEGATIVE else 0
        
        # Reversing values
        qty_in = orig_qty_out
        qty_out = orig_qty_in
        
        # Create Reversing Ledger Entry
        StockLedger.objects.create(
            product=adjustment.product,
            tx_type=(StockLedger.TransactionTypes.ADJ_POS if qty_in > 0 else StockLedger.TransactionTypes.ADJ_NEG),
            qty_in=qty_in,
            qty_out=qty_out,
            reference_type='ADJ-CANCEL',
            reference_id=adjustment.id,
            reference_number=adjustment.adjustment_number,
            remarks=f"Reversal of {adjustment.adjustment_number}",
            user=user
        )
        
        # Update Product Cache
        product = Product.objects.select_for_update().get(id=adjustment.product.id)
        product.current_stock += (qty_in - qty_out)
        product.save(update_fields=['current_stock'])
