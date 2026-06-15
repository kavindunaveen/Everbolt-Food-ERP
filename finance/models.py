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
            ("post_journal_entry", "Can post journal entries"),
        ]

class AccountType(models.TextChoices):
    ASSET = 'ASSET', 'Asset'
    LIABILITY = 'LIABILITY', 'Liability'
    EQUITY = 'EQUITY', 'Equity'
    REVENUE = 'REVENUE', 'Revenue'
    EXPENSE = 'EXPENSE', 'Expense'

class Account(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    account_type = models.CharField(max_length=20, choices=AccountType.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.code} - {self.name}"

    class Meta:
        ordering = ['code']

class JournalEntry(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        POSTED = 'POSTED', 'Posted'

    date = models.DateField()
    reference = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_balanced(self):
        debits = sum(line.debit for line in self.lines.all() if line.debit)
        credits = sum(line.credit for line in self.lines.all() if line.credit)
        return abs(debits - credits) < 0.01

    def __str__(self):
        return f"JE-{self.id} ({self.date})"
        
    class Meta:
        verbose_name_plural = "Journal Entries"
        ordering = ['-date', '-id']

class JournalEntryLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.CASCADE, related_name='lines')
    account = models.ForeignKey(Account, on_delete=models.PROTECT)
    description = models.CharField(max_length=255, blank=True, null=True)
    debit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    def __str__(self):
        return f"Line for {self.account.code} - {self.debit or self.credit}"
