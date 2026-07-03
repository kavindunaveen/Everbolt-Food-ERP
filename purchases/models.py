from django.db import models
from django.conf import settings
from decimal import Decimal
from inventory.models import Product

class GRN(models.Model):
    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    grn_number = models.CharField(max_length=50, unique=True, blank=True)
    po = models.ForeignKey('PurchaseOrder', on_delete=models.SET_NULL, null=True, blank=True, related_name='grns')

    # supplier_fk is the live FK to the Supplier model — use this for all filtering/reporting.
    # supplier (CharField below) is kept as a read-only snapshot for backward compatibility.
    supplier_fk = models.ForeignKey(
        'suppliers.Supplier',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='grns',
        verbose_name='Supplier'
    )
    supplier = models.CharField(max_length=200, blank=True,
                                help_text="Legacy text snapshot — do not edit manually")

    date = models.DateField()
    ref_number = models.CharField(max_length=100, blank=True, null=True, help_text="Supplier Invoice Number")
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        # Keep the text snapshot in sync with the FK whenever possible
        if self.supplier_fk and not self.supplier:
            self.supplier = self.supplier_fk.supplier_name
        if not self.grn_number:
            all_nums = GRN.objects.values_list('grn_number', flat=True)
            max_seq = 0
            for num in all_nums:
                try:
                    seq = int(num.split('-')[-1])
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
            self.grn_number = f"GRN-{max_seq + 1:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        name = self.supplier_fk.supplier_name if self.supplier_fk else self.supplier
        return f"{self.grn_number} - {name}"

class GRNItem(models.Model):
    grn = models.ForeignKey(GRN, on_delete=models.CASCADE, related_name='items')
    po_item = models.ForeignKey('PurchaseOrderItem', on_delete=models.SET_NULL, null=True, blank=True, related_name='grn_receipts')
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
                        last_seq = int(last_po.po_number.split('-')[-1])
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
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True, related_name='po_items')
    
    # Legacy text fields for older POs
    category = models.CharField(max_length=150, blank=True, null=True)
    sub_category = models.CharField(max_length=150, blank=True, null=True)
    material_code = models.CharField(max_length=100, blank=True, null=True)
    unit = models.CharField(max_length=50)
    qty = models.DecimalField(max_digits=12, decimal_places=3)
    received_qty = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    @property
    def amount(self):
        return Decimal(self.qty) * Decimal(self.unit_price)

    @property
    def remaining_qty(self):
        return self.qty - self.received_qty

    def save(self, *args, **kwargs):
        # Auto-generate material code for PM if not provided
        if self.po.po_type == POType.PACKING_MATERIAL and (not self.material_code or self.material_code == 'Auto-generated'):
            prefix = "PM-"
            with transaction.atomic():
                last_item = PurchaseOrderItem.objects.select_for_update().filter(material_code__startswith=prefix).order_by('-id').first()
                if last_item:
                    try:
                        last_seq_str = last_item.material_code.split('-')[-1]
                        last_seq = int(last_seq_str)
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                self.material_code = f"{prefix}{new_seq:04d}"
        
        # Auto-generate material code for custom RM
        elif self.po.po_type == POType.RAW_MATERIAL and self.material_code == 'Auto-generated':
            cat_map = {
                'herbs': 'RM-HRB-',
                'flavours': 'RM-FLV-',
                'other': 'RM-OTH-'
            }
            prefix = cat_map.get(self.category, 'RM-CUST-')
            with transaction.atomic():
                last_item = PurchaseOrderItem.objects.select_for_update().filter(material_code__startswith=prefix).order_by('-id').first()
                if last_item:
                    try:
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
