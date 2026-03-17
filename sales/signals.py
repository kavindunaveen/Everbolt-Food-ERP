from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import InvoiceItem, Return

@receiver(post_save, sender=InvoiceItem)
def decrement_stock_on_invoice(sender, instance, created, **kwargs):
    """
    When an InvoiceItem is created, deduct the quantity from the Product's current_stock.
    """
    if created:
        product = instance.product
        product.current_stock -= instance.quantity
        
        # If stock logic dictates it should go out of stock
        if product.current_stock <= 0:
            product.status = False
            
        product.save()

@receiver(post_delete, sender=InvoiceItem)
def increment_stock_on_invoice_delete(sender, instance, **kwargs):
    """
    If an InvoiceItem is completely deleted (e.g. order cancelled and cleared), 
    return the stock.
    """
    product = instance.product
    product.current_stock += instance.quantity
    
    if product.current_stock > 0:
        product.status = True
        
    product.save()

@receiver(post_save, sender=Return)
def handle_stock_on_return(sender, instance, created, **kwargs):
    """
    When a Return is logged, if the condition is SELLABLE and stock hasn't been updated yet,
    add the stock back to the inventory.
    """
    # Only process if this return is new OR if stock hasn't been updated yet
    if not instance.stock_updated and instance.condition == Return.Condition.SELLABLE:
        product = instance.returned_product
        product.current_stock += instance.quantity
        
        if product.current_stock > 0:
            product.status = True
            
        product.save()
        
        # Mark as updated to prevent double counting if the return record is edited later
        # We use .update() to avoid triggering the save() signal recursively
        Return.objects.filter(pk=instance.pk).update(stock_updated=True)
