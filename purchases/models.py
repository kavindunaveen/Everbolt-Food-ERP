from django.db import models
from django.conf import settings
from inventory.models import Product

class GRN(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    grn_number = models.CharField(max_length=50, unique=True, blank=True)
    supplier = models.CharField(max_length=200)
    date = models.DateField()
    ref_number = models.CharField(max_length=100, blank=True, null=True, help_text="Supplier Invoice Number")
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.grn_number:
            last_grn = GRN.objects.order_by('-id').first()
            if last_grn and last_grn.grn_number.startswith('GRN-'):
                try:
                    seq = int(last_grn.grn_number.split('-')[1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.grn_number = f"GRN-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.grn_number} - {self.supplier}"

class GRNItem(models.Model):
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    batch = models.CharField(max_length=50, blank=True, null=True)
    expiry = models.DateField(blank=True, null=True)

    def __str__(self):
        return f"{self.grn.grn_number} - {self.product.name} ({self.qty})"
