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
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000, help_text="Amount before tax and rounding")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    total_discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    custom_discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    custom_discount_value = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    notes = models.TextField(blank=True, null=True)
    is_converted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.quotation_number:
            # Keep original monthly prefix format e.g. "26MAY_EBFQ_"
            # BUT find the global max sequence across ALL quotations ever
            # so the number never resets when the month changes.
            prefix = timezone.now().strftime("%y%b").upper() + "_EBFQ_"
            with transaction.atomic():
                all_numbers = Quotation.objects.select_for_update().values_list('quotation_number', flat=True)
                max_seq = 483  # Floor: next will be 484
                for num in all_numbers:
                    try:
                        seq = int(num.split('_')[-1])
                        if seq > max_seq:
                            max_seq = seq
                    except (ValueError, IndexError):
                        pass
                self.quotation_number = f"{prefix}{max_seq + 1:05d}"
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
        CASH   = 'CASH',   'Cash'
        COD    = 'COD',    'Cash On Delivery'
        CREDIT = 'CREDIT', 'Credit Invoice'

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
    subtotal_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000, help_text="Amount before tax and rounding")
    tax_amount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    total_discount = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    custom_discount_type = models.CharField(max_length=10, choices=[('AMOUNT', 'Amount'), ('PERCENT', 'Percentage')], default='AMOUNT')
    custom_discount_value = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, null=True)
    reviewer_notes = models.TextField(blank=True, null=True, help_text="Notes from the approver/manager")
    cancellation_reason = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        from datetime import timedelta

        # Only calculate due_date on first creation (when it has never been set).
        # Subsequent saves (status changes, edits, approvals) must NEVER overwrite it
        # so the original accounting due date is preserved.
        if not self.due_date:
            days = 0
            if self.invoice_type == 'COD':
                days = 0
            elif self.invoice_type == 'CASH':
                days = 0  # Due immediately on cash sales
            elif self.invoice_type == 'CREDIT':
                terms = self.customer.payment_terms
                if terms == 'COD':
                    days = 0
                elif terms and terms.startswith('CREDIT_'):
                    try:
                        days = int(terms.split('_')[1])
                    except (IndexError, ValueError):
                        days = 30
                elif terms == 'CASH':
                    days = 0
                else:
                    days = 30

            base_date = timezone.now().date()
            self.due_date = base_date + timedelta(days=days)

        if not self.invoice_number:
            # Keep original monthly prefix format e.g. "26MAY_EBFR_"
            # BUT find the global max sequence across ALL invoices ever
            # so the number never resets when the month changes.
            prefix = timezone.now().strftime("%y%b").upper() + "_EBFR_"
            with transaction.atomic():
                all_numbers = Invoice.objects.select_for_update().values_list('invoice_number', flat=True)
                max_seq = 314  # Floor: next will be 315
                for num in all_numbers:
                    try:
                        seq = int(num.split('_')[-1])
                        if seq > max_seq:
                            max_seq = seq
                    except (ValueError, IndexError):
                        pass
                self.invoice_number = f"{prefix}{max_seq + 1:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} ({self.get_invoice_type_display()})"

    @property
    def is_overdue(self):
        # CASH and COD are typically completed on the same day, so they shouldn't show as overdue
        if self.invoice_type in ['CASH', 'COD']:
            return False
        if self.status == 'ISSUED' and self.due_date and self.due_date < timezone.now().date():
            return True
        return False

    def delete(self, *args, **kwargs):
        # Always clean up stock reserves before deleting an invoice.
        # This covers DRAFT invoices deleted directly — without this,
        # ghost reserves would block inventory for other orders.
        from inventory.models import StockReserve
        StockReserve.objects.filter(reference_type='INV', reference_id=self.pk).delete()
        super().delete(*args, **kwargs)

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
    original_invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='returns')
    returned_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=5, default=0.00000,
                                     help_text="Price per unit at time of return (used for credit note value)")
    reason = models.CharField(max_length=50, choices=ReturnReason.choices)
    condition = models.CharField(max_length=50, choices=Condition.choices)
    notes = models.TextField(blank=True, null=True)

    credit_note_issued = models.BooleanField(default=False)
    stock_updated = models.BooleanField(default=False, help_text="True if stock was added back")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_date = models.DateTimeField(auto_now_add=True, null=True, blank=True)

    @property
    def credit_value(self):
        from decimal import Decimal
        return Decimal(self.quantity) * Decimal(self.unit_price)

    def save(self, *args, **kwargs):
        if not self.return_number:
            all_nums = Return.objects.values_list('return_number', flat=True)
            max_seq = 0
            for num in all_nums:
                try:
                    seq = int(num.split('-')[-1])
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
            self.return_number = f"RTN-{max_seq + 1:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.return_number


class CreditNote(models.Model):
    credit_note_number = models.CharField(max_length=50, unique=True, blank=True)
    return_record = models.OneToOneField(Return, on_delete=models.PROTECT, related_name='credit_note')
    original_invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name='credit_notes')
    customer = models.ForeignKey('crm.Customer', on_delete=models.PROTECT)

    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=5)
    credit_amount = models.DecimalField(max_digits=12, decimal_places=5)

    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    issued_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.credit_note_number:
            all_nums = CreditNote.objects.values_list('credit_note_number', flat=True)
            max_seq = 0
            for num in all_nums:
                try:
                    seq = int(num.split('-')[-1])
                    if seq > max_seq:
                        max_seq = seq
                except (ValueError, IndexError):
                    pass
            self.credit_note_number = f"CN-{max_seq + 1:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.credit_note_number

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

    dn_number = models.CharField(max_length=50, unique=True)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='delivery_notes')
    
    # These are populated from the invoice but stored here for snapshot/record integrity
    customer_name = models.CharField(max_length=200)
    delivery_address = models.TextField()
    delivery_date = models.DateField()
    
    delivered_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    
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
    quantity = models.PositiveIntegerField(help_text="Actual quantity delivered in this DN")
    invoiced_quantity = models.PositiveIntegerField(
        default=0,
        help_text="Original invoiced quantity — used to cap delivery and track partial delivery"
    )

    @property
    def is_partial(self):
        """True if less than the full invoiced quantity was delivered."""
        return self.quantity < self.invoiced_quantity

    @property
    def is_over_delivered(self):
        """True if DN quantity exceeds what was invoiced — should never happen."""
        return self.quantity > self.invoiced_quantity

    def __str__(self):
        return f"{self.product.name} ({self.quantity}/{self.invoiced_quantity})"
