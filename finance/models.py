from django.db import models, transaction
from django.conf import settings
from sales.models import Invoice

class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CHEQUE = 'CHEQUE', 'Cheque'
        CARD = 'CARD', 'Credit/Debit Card'
        OTHER = 'OTHER', 'Other'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=5)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Cheque number, Bank transfer ID")
    notes = models.TextField(blank=True, null=True)
    
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        is_new = self.pk is None
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Check if invoice is fully paid
            invoice = self.invoice
            total_paid = sum(p.amount for p in invoice.payments.all())
            
            if total_paid >= invoice.total_amount and invoice.status != Invoice.Status.PAID:
                invoice.status = Invoice.Status.PAID
                invoice.save(update_fields=['status'])

    def __str__(self):
        return f"Payment {self.id} for {self.invoice.invoice_number}"

    class Meta:
        permissions = [
            ("manage_finance", "Can access the finance module"),
        ]
