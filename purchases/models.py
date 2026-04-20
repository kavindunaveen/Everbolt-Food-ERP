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

from suppliers.models import Supplier
from django.db import transaction

class POType(models.TextChoices):
    RAW_MATERIAL = 'RAW_MATERIAL', 'Raw Material'
    PACKING_MATERIAL = 'PACKING_MATERIAL', 'Packing Material'

class PurchaseOrder(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    class PaymentTermChoices(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit'
        CASH = 'CASH', 'Cash'
        ADVANCE = 'ADVANCE', 'Advance'

    po_number = models.CharField(max_length=50, unique=True, blank=True)
    po_type = models.CharField(max_length=25, choices=POType.choices)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    
    attention = models.CharField(max_length=150, blank=True, null=True, help_text="Contact person")
    payment_term = models.CharField(max_length=20, choices=PaymentTermChoices.choices, default=PaymentTermChoices.CREDIT)
    apply_vat = models.BooleanField(default=False, help_text="Apply 18% VAT")

    date = models.DateField()
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    remarks = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def sub_total(self):
        return sum(item.amount for item in self.items.all())

    @property
    def vat_amount(self):
        if self.apply_vat:
            return self.sub_total * Decimal('0.18')
        return Decimal('0.00')

    @property
    def grand_total(self):
        return self.sub_total + self.vat_amount

    def save(self, *args, **kwargs):
        if not self.po_number:
            prefix = "EFPO-"
            with transaction.atomic():
                last_po = PurchaseOrder.objects.select_for_update().filter(po_number__startswith=prefix).order_by('-po_number').first()
                if last_po:
                    try:
                        last_seq = int(last_po.po_number.split('-')[1])
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                self.po_number = f"{prefix}{new_seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po_number} - {self.supplier.supplier_name}"

from decimal import Decimal

class PurchaseOrderItem(models.Model):
    po = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    category = models.CharField(max_length=150)
    sub_category = models.CharField(max_length=150, blank=True, null=True)
    material_code = models.CharField(max_length=100)
    unit = models.CharField(max_length=50)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    @property
    def amount(self):
        return Decimal(self.qty) * Decimal(self.unit_price)

    def save(self, *args, **kwargs):
        # Auto-generate material code for PM if not provided
        if self.po.po_type == POType.PACKING_MATERIAL and not self.material_code.startswith('PM-'):
            prefix = "PM-"
            with transaction.atomic():
                # Get last PM- code in the entire system to ensure sequential uniqueness
                last_item = PurchaseOrderItem.objects.select_for_update().filter(material_code__startswith=prefix).order_by('-id').first()
                if last_item:
                    try:
                        # Ensure we parse properly, sometimes code could be PM-0001
                        # We just take the last 4 characters and try to int it.
                        last_seq_str = last_item.material_code.split('-')[-1]
                        last_seq = int(last_seq_str)
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                self.material_code = f"{prefix}{new_seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.po.po_number} - {self.material_code}"
