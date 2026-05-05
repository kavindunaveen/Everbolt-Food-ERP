from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from crm.models import Customer
from inventory.models import Product

class Quotation(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        SENT = 'SENT', 'Sent to Customer'
        EXPIRED = 'EXPIRED', 'Expired'
        CONVERTED = 'CONVERTED', 'Converted to Invoice'
        CANCELLED = 'CANCELLED', 'Cancelled'

    quotation_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    creation_date = models.DateTimeField(auto_now_add=True)
    valid_until = models.DateField()
    customer_po_number = models.CharField(max_length=50, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    total_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    total_discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    custom_discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    custom_discount_value = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    notes = models.TextField(blank=True, null=True)
    is_converted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            now = timezone.now()
            prefix = now.strftime("%y%b").upper() + "_EBFQ_"
            with transaction.atomic():
                last_quote = Quotation.objects.select_for_update().filter(quotation_number__startswith=prefix).order_by('-quotation_number').first()
                if last_quote:
                    last_seq = int(last_quote.quotation_number.split('_')[-1])
                    new_seq = last_seq + 1
                else:
                    new_seq = 484
                self.quotation_number = f"{prefix}{new_seq:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.quotation_number

    @property
    def is_late(self):
        if self.status in ['DRAFT', 'SENT'] and self.valid_until < timezone.now().date():
            return True
        return False

class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT, null=True, blank=True)
    custom_product_name = models.CharField(max_length=255, blank=True, null=True)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=5)
    discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    line_total = models.DecimalField(max_digits=12, decimal_places=5)

    @property
    def get_discount_amount(self):
        from decimal import Decimal
        val = self.discount or Decimal('0.00')
        if self.discount_type == 'PERCENT':
            return (self.quantity * self.unit_price) * (val / Decimal('100.0'))
        return val

    @property
    def amount_ex_vat(self):
        return self.line_total - self.tax_amount

class Invoice(models.Model):
    class Type(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit Invoice'
        COD = 'COD', 'Cash On Delivery'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        APPROVAL_PENDING = 'APPROVAL_PENDING', 'Pending Approval'
        ISSUED = 'ISSUED', 'Issued'
        PAID = 'PAID', 'Paid'
        EDIT_PENDING = 'EDIT_PENDING', 'Edit Pending'
        CANCEL_PENDING = 'CANCEL_PENDING', 'Cancellation Pending'
        CANCELLED = 'CANCELLED', 'Cancelled'

    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=Type.choices, default=Type.CREDIT)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    designated_approver = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoices_to_approve')
    is_approved = models.BooleanField(default=False)
    
    creation_date = models.DateTimeField(auto_now_add=True)
    delivery_date = models.DateField(blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    customer_po_number = models.CharField(max_length=50, blank=True, null=True)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    total_discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    custom_discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    custom_discount_value = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, null=True)
    reviewer_notes = models.TextField(blank=True, null=True, help_text="Notes from the approver/manager")
    cancellation_reason = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            now = timezone.now()
            prefix = now.strftime("%y%b").upper() + "_EBFR_"
            with transaction.atomic():
                last_invoice = Invoice.objects.select_for_update().filter(invoice_number__startswith=prefix).order_by('-invoice_number').first()
                if last_invoice:
                    last_seq = int(last_invoice.invoice_number.split('_')[-1])
                    new_seq = last_seq + 1
                else:
                    new_seq = 315
                self.invoice_number = f"{prefix}{new_seq:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} ({self.get_invoice_type_display()})"

    @property
    def is_overdue(self):
        if self.status == 'ISSUED' and self.due_date and self.due_date < timezone.now().date():
            return True
        return False

    class Meta:
        permissions = [
            ("approve_invoice", "Can approve pending invoices"),
        ]

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=5)
    discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    line_total = models.DecimalField(max_digits=12, decimal_places=5)

    @property
    def get_discount_amount(self):
        from decimal import Decimal
        val = self.discount or Decimal('0.00')
        if self.discount_type == 'PERCENT':
            return (self.quantity * self.unit_price) * (val / Decimal('100.0'))
        return val

    @property
    def amount_ex_vat(self):
        return self.line_total - self.tax_amount


class Return(models.Model):
    class ReturnReason(models.TextChoices):
        DAMAGED_PACK = 'DAMAGED_PACK', 'Damaged Pack'
        WRONG_ITEM = 'WRONG_ITEM', 'Wrong Item'
        NEAR_EXPIRY = 'NEAR_EXPIRY', 'Near Expiry'
        QUALITY = 'QUALITY', 'Quality Complaint'

    class Condition(models.TextChoices):
        SELLABLE = 'SELLABLE', 'Good / Sellable'
        DAMAGED = 'DAMAGED', 'Damaged / Unsellable'

    return_number = models.CharField(max_length=50, unique=True, blank=True)
    original_invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    returned_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=50, choices=ReturnReason.choices)
    condition = models.CharField(max_length=50, choices=Condition.choices)
    
    credit_note_issued = models.BooleanField(default=False)
    stock_updated = models.BooleanField(default=False, help_text="True if stock was added back")
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.return_number:
            last_return = Return.objects.order_by('-id').first()
            if last_return and last_return.return_number.startswith('RTN-'):
                try:
                    seq = int(last_return.return_number.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.return_number = f"RTN-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.return_number
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class SalesAuditLog(models.Model):
    # Link to any sales-related model (Invoice, Quotation, Return)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    action = models.CharField(max_length=100)  # e.g., "Status Changed"
    old_value = models.CharField(max_length=100, blank=True, null=True)
    new_value = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.action} on {self.content_object} by {self.user}"

class DeliveryNote(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending'
        DELIVERED = 'DELIVERED', 'Delivered'
        PARTIAL = 'PARTIAL', 'Partial'
        FAILED = 'FAILED', 'Failed'

    class DeliveryPerson(models.TextChoices):
        SUMITH = 'SUMITH', 'Sumith'
        ASANGA = 'ASANGA', 'Asanga'
        CHAMINDA = 'CHAMINDA', 'Chaminda'
        KESHAN = 'KESHAN', 'Keshan'
        MANISTHA = 'MANISTHA', 'Manistha'
        OTHER = 'OTHER', 'Other'

    dn_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='delivery_notes')
    
    # These are populated from the invoice but stored here for snapshot/record integrity
    customer_name = models.CharField(max_length=200)
    delivery_address = models.TextField()
    delivery_date = models.DateField()
    
    delivered_by = models.CharField(max_length=50, choices=DeliveryPerson.choices)
    other_delivery_person = models.CharField(max_length=150, blank=True, null=True, help_text="Fill if 'Other' is selected")
    
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    remarks = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.dn_number:
            now = timezone.now()
            prefix = now.strftime("%y%b").upper() + "_EBDN_"
            with transaction.atomic():
                last_dn = DeliveryNote.objects.select_for_update().filter(dn_number__startswith=prefix).order_by('-dn_number').first()
                if last_dn:
                    last_seq = int(last_dn.dn_number.split('_')[-1])
                    new_seq = last_seq + 1
                else:
                    new_seq = 1
                self.dn_number = f"{prefix}{new_seq:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.dn_number

class DeliveryNoteItem(models.Model):
    delivery_note = models.ForeignKey(DeliveryNote, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.product.name} ({self.quantity})"
