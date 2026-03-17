from django.db import models, transaction
from django.conf import settings
from django.utils import timezone
from crm.models import Customer
from inventory.models import Product

class Quotation(models.Model):
    quotation_number = models.CharField(max_length=50, unique=True)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    creation_date = models.DateField(auto_now_add=True)
    valid_until = models.DateField()
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True, null=True)

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
                    new_seq = 1
                self.quotation_number = f"{prefix}{new_seq:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.quotation_number

class QuotationItem(models.Model):
    quotation = models.ForeignKey(Quotation, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

class Invoice(models.Model):
    class Type(models.TextChoices):
        CREDIT = 'CREDIT', 'Credit Invoice'
        COD = 'COD', 'Cash On Delivery'

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ISSUED = 'ISSUED', 'Issued'
        PAID = 'PAID', 'Paid'
        CANCELLED = 'CANCELLED', 'Cancelled'

    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=Type.choices, default=Type.CREDIT)
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    salesperson = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    
    creation_date = models.DateField(auto_now_add=True)
    delivery_date = models.DateField(blank=True, null=True)
    
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    notes = models.TextField(blank=True, null=True)

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
                    new_seq = 1
                self.invoice_number = f"{prefix}{new_seq:05d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.invoice_number} ({self.get_invoice_type_display()})"

class InvoiceItem(models.Model):
    invoice = models.ForeignKey(Invoice, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)


class Return(models.Model):
    class ReturnReason(models.TextChoices):
        DAMAGED_PACK = 'DAMAGED_PACK', 'Damaged Pack'
        WRONG_ITEM = 'WRONG_ITEM', 'Wrong Item'
        NEAR_EXPIRY = 'NEAR_EXPIRY', 'Near Expiry'
        QUALITY = 'QUALITY', 'Quality Complaint'

    class Condition(models.TextChoices):
        SELLABLE = 'SELLABLE', 'Good / Sellable'
        DAMAGED = 'DAMAGED', 'Damaged / Unsellable'

    return_number = models.CharField(max_length=50, unique=True)
    original_invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT)
    returned_product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    reason = models.CharField(max_length=50, choices=ReturnReason.choices)
    condition = models.CharField(max_length=50, choices=Condition.choices)
    
    credit_note_issued = models.BooleanField(default=False)
    stock_updated = models.BooleanField(default=False, help_text="True if stock was added back")

    def __str__(self):
        return self.return_number
