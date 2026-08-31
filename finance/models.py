from django.db import models, transaction
from django.conf import settings
from sales.models import Invoice

class BankAccount(models.Model):
    bank_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=50)
    branch = models.CharField(max_length=100, blank=True, null=True)
    ledger_account = models.OneToOneField('Account', on_delete=models.PROTECT, related_name='bank_account', help_text="The Chart of Accounts Asset linked to this bank account.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.bank_name} - {self.account_number}"

class Payment(models.Model):
    class PaymentMethod(models.TextChoices):
        CASH = 'CASH', 'Cash'
        BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
        CHEQUE = 'CHEQUE', 'Cheque'
        CARD = 'CARD', 'Credit/Debit Card'
        CREDIT_NOTE = 'CREDIT_NOTE', 'Credit Note'
        OTHER = 'OTHER', 'Other'

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.BANK_TRANSFER)
    reference_number = models.CharField(max_length=100, blank=True, null=True, help_text="e.g. Cheque number, Bank transfer ID")
    slip_attachment = models.FileField(upload_to='payment_slips/', blank=True, null=True, help_text="Image or PDF of the payment slip")
    notes = models.TextField(blank=True, null=True)
    
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    bank_account = models.ForeignKey(BankAccount, on_delete=models.SET_NULL, null=True, blank=True, related_name='payments')
    created_at = models.DateTimeField(auto_now_add=True)

    class ReconciliationStatus(models.TextChoices):
        UNRECONCILED = 'UNRECONCILED', 'Unreconciled'
        RECONCILED = 'RECONCILED', 'Reconciled'
        DISPUTED = 'DISPUTED', 'Disputed'

    reconciliation_status = models.CharField(
        max_length=20,
        choices=ReconciliationStatus.choices,
        default=ReconciliationStatus.UNRECONCILED,
        db_index=True
    )
    reconciled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='reconciled_payments'
    )
    reconciled_at = models.DateTimeField(null=True, blank=True)
    reconciliation_note = models.TextField(blank=True, null=True)

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            
            # Re-fetch total paid from DB (including this new payment) to avoid stale reads
            from django.db.models import Sum
            from django.db.models.functions import Coalesce
            from decimal import Decimal
            invoice = self.invoice
            total_paid = invoice.payments.aggregate(
                t=Coalesce(Sum('amount'), Decimal('0.00'))
            )['t']
            
            if total_paid >= invoice.total_amount - Decimal('0.01') and invoice.status != Invoice.Status.PAID:
                invoice.status = Invoice.Status.PAID
                invoice.save(update_fields=['status'])

    def __str__(self):
        return f"Payment {self.id} for {self.invoice.invoice_number}"

class FinanceModule(models.Model):
    class Meta:
        managed = False
        default_permissions = ()
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

class CustomerCredit(models.Model):
    customer = models.ForeignKey('crm.Customer', on_delete=models.CASCADE, related_name='credits')
    original_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_amount = models.DecimalField(max_digits=12, decimal_places=2)
    notes = models.TextField(blank=True, null=True, help_text="Reason for credit (e.g. Overpayment on Invoice #1023)")
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"Credit for {self.customer.customer_name} - Rs {self.remaining_amount}"

    @property
    def related_invoice(self):
        if self.notes and self.notes.startswith("Overpayment on Invoice "):
            import re
            match = re.search(r"Invoice ([\w_]+)", self.notes)
            if match:
                inv_num = match.group(1)
                from sales.models import Invoice
                return Invoice.objects.filter(invoice_number=inv_num).first()
        return None

    @property
    def overpayment_details(self):
        invoice = self.related_invoice
        if invoice:
            return {
                'invoice_total': invoice.total_amount,
                'total_paid': invoice.total_amount + self.original_amount,
                'overpayment': self.original_amount
            }
        return None

    class Meta:
        ordering = ['-created_at']

class CreditApplication(models.Model):
    customer_credit = models.ForeignKey(CustomerCredit, on_delete=models.CASCADE, related_name='applications')
    invoice = models.ForeignKey('sales.Invoice', on_delete=models.CASCADE, related_name='credit_applications')
    amount_applied = models.DecimalField(max_digits=12, decimal_places=2)
    applied_at = models.DateTimeField(auto_now_add=True)
    applied_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return f"Applied Rs {self.amount_applied} to {self.invoice.invoice_number}"

    class Meta:
        ordering = ['-applied_at']
