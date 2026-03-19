from django.db import transaction
from django.shortcuts import get_object_or_404
from .models import Production, ProductionMaterial, ProductionOutput
from inventory.models import StockLedger, Product

def confirm_production(production, user):
    """
    Confirms a Production / Conversion entry.
    - Reduces stock for materials used (PROD_CONS).
    - Increases stock for products produced (PROD_OUT).
    - Updates Product current_stock caches.
    """
    if production.status != Production.StatusChoices.DRAFT:
        raise ValueError("Only DRAFT production entries can be confirmed.")
        
    with transaction.atomic():
        production.status = Production.StatusChoices.CONFIRMED
        production.save(update_fields=['status', 'updated_at'])
        
        ledgers = []
        
        # 1. Handle Materials (Consumption)
        for mat in production.materials.all():
            qty = mat.actual_used_qty
            if qty > 0:
                ledgers.append(StockLedger(
                    product=mat.component_product,
                    tx_type=StockLedger.TransactionTypes.PROD_CONS,
                    qty_in=0,
                    qty_out=qty,
                    reference_type='PROD',
                    reference_id=production.id,
                    reference_number=production.production_number,
                    remarks=f"Consumed for production {production.production_number}",
                    user=user
                ))
                
                # Check for negative stock if allowed
                prod_obj = Product.objects.select_for_update().get(id=mat.component_product.id)
                if not prod_obj.allow_negative_stock and prod_obj.current_stock < qty:
                    raise ValueError(f"Insufficient stock for {prod_obj.name}. Required: {qty}, Available: {prod_obj.current_stock}")
                
                prod_obj.current_stock -= qty
                prod_obj.save(update_fields=['current_stock'])
        
        # 2. Handle Outputs (Production)
        for out in production.outputs.all():
            qty = out.produced_qty
            if qty > 0:
                ledgers.append(StockLedger(
                    product=out.output_product,
                    tx_type=StockLedger.TransactionTypes.PROD_OUT,
                    qty_in=qty,
                    qty_out=0,
                    reference_type='PROD',
                    reference_id=production.id,
                    reference_number=production.production_number,
                    remarks=f"Produced via {production.production_number}",
                    user=user
                ))
                
                prod_obj = Product.objects.select_for_update().get(id=out.output_product.id)
                prod_obj.current_stock += qty
                prod_obj.save(update_fields=['current_stock'])
                
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)

def cancel_production(production, user):
    """
    Cancels a CONFIRMED Production entry by reversing the stock movements.
    """
    if production.status != Production.StatusChoices.CONFIRMED:
        raise ValueError("Only CONFIRMED production entries can be cancelled.")
        
    with transaction.atomic():
        production.status = Production.StatusChoices.CANCELLED
        production.save(update_fields=['status', 'updated_at'])
        
        ledgers = []
        
        # 1. Reverse Materials (Add back stock)
        for mat in production.materials.all():
            qty = mat.actual_used_qty
            if qty > 0:
                ledgers.append(StockLedger(
                    product=mat.component_product,
                    tx_type=StockLedger.TransactionTypes.PROD_CONS,
                    qty_in=qty, # Reversing consumption
                    qty_out=0,
                    reference_type='PROD-CANCEL',
                    reference_id=production.id,
                    reference_number=production.production_number,
                    remarks=f"Reversal of consumption for {production.production_number}",
                    user=user
                ))
                
                prod_obj = Product.objects.select_for_update().get(id=mat.component_product.id)
                prod_obj.current_stock += qty
                prod_obj.save(update_fields=['current_stock'])
        
        # 2. Reverse Outputs (Remove stock)
        for out in production.outputs.all():
            qty = out.produced_qty
            if qty > 0:
                ledgers.append(StockLedger(
                    product=out.output_product,
                    tx_type=StockLedger.TransactionTypes.PROD_OUT,
                    qty_in=0,
                    qty_out=qty, # Reversing production
                    reference_type='PROD-CANCEL',
                    reference_id=production.id,
                    reference_number=production.production_number,
                    remarks=f"Reversal of production for {production.production_number}",
                    user=user
                ))
                
                prod_obj = Product.objects.select_for_update().get(id=out.output_product.id)
                prod_obj.current_stock -= qty
                prod_obj.save(update_fields=['current_stock'])
                
        if ledgers:
            StockLedger.objects.bulk_create(ledgers)
