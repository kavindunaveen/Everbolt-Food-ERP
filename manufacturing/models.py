from django.db import models
from django.conf import settings
from inventory.models import Product

class BOM(models.Model):
    bom_code = models.CharField(max_length=50, unique=True, blank=True)
    finished_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='boms')
    version = models.CharField(max_length=10, default='1.0')
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.bom_code:
            self.bom_code = f"BOM-{self.finished_product.sku}-{self.version}"
        
        # Ensure only one active BOM per product
        if self.is_active:
            BOM.objects.filter(finished_product=self.finished_product, is_active=True).exclude(pk=self.pk).update(is_active=False)
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bom_code} ({self.finished_product.name})"

class BOMItem(models.Model):
    bom = models.ForeignKey(BOM, on_delete=models.CASCADE, related_name='items')
    component_product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='used_in_boms')
    qty_required = models.DecimalField(max_digits=12, decimal_places=3)
    
    def __str__(self):
        return f"{self.bom.bom_code} -> {self.component_product.name} ({self.qty_required})"

class Production(models.Model):
    class ConversionTypes(models.TextChoices):
        MANUFACTURING = 'MANUFACTURING', 'Manufacturing'
        REPACKING = 'REPACKING', 'Repacking'
        BLENDING = 'BLENDING', 'Blending'

    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    production_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    conversion_type = models.CharField(max_length=20, choices=ConversionTypes.choices, default=ConversionTypes.MANUFACTURING)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    
    notes = models.TextField(blank=True, null=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.production_number:
            last_prod = Production.objects.order_by('-id').first()
            if last_prod and last_prod.production_number.startswith('PROD-'):
                try:
                    seq = int(last_prod.production_number.split('-')[1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.production_number = f"PROD-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.production_number} ({self.conversion_type})"

class ProductionMaterial(models.Model):
    production = models.ForeignKey(Production, on_delete=models.CASCADE, related_name='materials')
    component_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    required_qty = models.DecimalField(max_digits=12, decimal_places=3)
    actual_used_qty = models.DecimalField(max_digits=12, decimal_places=3)
    wastage_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)

    def __str__(self):
        return f"{self.production.production_number} - Material: {self.component_product.name}"

class ProductionOutput(models.Model):
    production = models.ForeignKey(Production, on_delete=models.CASCADE, related_name='outputs')
    output_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    produced_qty = models.DecimalField(max_digits=12, decimal_places=3)

    def __str__(self):
        return f"{self.production.production_number} - Output: {self.output_product.name}"
