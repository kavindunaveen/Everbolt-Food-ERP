from django.db import models, transaction
from django.conf import settings

class CustomerType(models.TextChoices):
    HOTELS = 'HOTELS', 'Hotels'
    VILLAS = 'VILLAS', 'Villas'
    APARTMENTS = 'APARTMENTS', 'Apartments'
    CAFES = 'CAFES', 'Cafes'
    RESTAURANTS = 'RESTAURANTS', 'Restaurants'
    SUPERMARKETS = 'SUPERMARKETS', 'Supermarkets'
    DISTRIBUTORS = 'DISTRIBUTORS', 'Distributors / Wholesalers'
    EXPORTS = 'EXPORTS', 'Exports'
    CORPORATE = 'CORPORATE', 'Corporate'
    HOSPITALS = 'HOSPITALS', 'Hospitals'
    ACADEMIC = 'ACADEMIC', 'Academic Institutions'
    BANKS = 'BANKS', 'Banks'
    OTHER = 'OTHER', 'Other'

class PaymentTerms(models.TextChoices):
    CASH = 'CASH', 'Cash'
    COD = 'COD', 'COD'
    CREDIT_7 = 'CREDIT_7', 'Credit - 7 days'
    CREDIT_15 = 'CREDIT_15', 'Credit - 15 days'
    CREDIT_30 = 'CREDIT_30', 'Credit - 30 days'
    CREDIT_45 = 'CREDIT_45', 'Credit - 45 days'
    CREDIT_60 = 'CREDIT_60', 'Credit - 60 days'

class OrderType(models.TextChoices):
    CAMPAIGN = 'CAMPAIGN', 'Campaign'
    DIRECT_CONTACT = 'DIRECT_CONTACT', 'Direct Contact'
    SHOWROOM = 'SHOWROOM', 'Showroom'

class PaymentMethod(models.TextChoices):
    CASH = 'CASH', 'Cash'
    CHEQUE = 'CHEQUE', 'Cheque'
    BANK_TRANSFER = 'BANK_TRANSFER', 'Bank Transfer'
    DIRECT_DEPOSIT = 'DIRECT_DEPOSIT', 'Direct Deposit'

class CustomerStatus(models.TextChoices):
    ACTIVE = 'ACTIVE', 'Active'
    INACTIVE = 'INACTIVE', 'Inactive'
    BLACKLIST = 'BLACKLIST', 'Blacklist'
    ONHOLD = 'ONHOLD', 'On Hold'

class ProvinceChoices(models.TextChoices):
    WESTERN = 'WESTERN', 'Western Province'
    CENTRAL = 'CENTRAL', 'Central Province'
    SOUTHERN = 'SOUTHERN', 'Southern Province'
    UVA = 'UVA', 'Uva Province'
    SABARAGAMUWA = 'SABARAGAMUWA', 'Sabaragamuwa Province'
    NORTH_WESTERN = 'NORTH_WESTERN', 'North Western Province'
    NORTH_CENTRAL = 'NORTH_CENTRAL', 'North Central Province'
    NORTHERN = 'NORTHERN', 'Northern Province'
    EASTERN = 'EASTERN', 'Eastern Province'

class Customer(models.Model):
    customer_code = models.CharField(max_length=50, unique=True, blank=True)
    customer_name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    contact_person = models.CharField(max_length=150)
    phone = models.CharField(max_length=50)
    phone_secondary = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    
    billing_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    billing_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    billing_city = models.CharField(max_length=100, blank=True, null=True)
    billing_province = models.CharField(max_length=100, choices=ProvinceChoices.choices, blank=True, null=True)
    billing_zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    delivery_address_line1 = models.CharField(max_length=255, blank=True, null=True)
    delivery_address_line2 = models.CharField(max_length=255, blank=True, null=True)
    delivery_city = models.CharField(max_length=100, blank=True, null=True)
    delivery_province = models.CharField(max_length=100, choices=ProvinceChoices.choices, blank=True, null=True)
    delivery_zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    customer_type = models.CharField(max_length=50, choices=CustomerType.choices)
    custom_customer_type = models.CharField(max_length=150, blank=True, null=True)
    
    assigned_sales_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=False, related_name='customers')
    order_type = models.CharField(max_length=50, choices=OrderType.choices, blank=True, null=True)
    
    payment_terms = models.CharField(max_length=50, choices=PaymentTerms.choices, default=PaymentTerms.CASH)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    special_price_customer = models.BooleanField(default=False)
    payment_method = models.CharField(max_length=50, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    customer_status = models.CharField(max_length=50, choices=CustomerStatus.choices, default=CustomerStatus.ACTIVE)
    
    registration_date = models.DateField(auto_now_add=True)
    vat_enabled = models.BooleanField(default=True, help_text="Always compute 18% VAT")
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    tin_number = models.CharField(max_length=50, blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.customer_code:
            prefix = "FC"
            with transaction.atomic():
                last_customer = Customer.objects.select_for_update().filter(customer_code__startswith=prefix).order_by('-customer_code').first()
                if last_customer:
                    try:
                        last_seq = int(last_customer.customer_code.replace(prefix, ""))
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                self.customer_code = f"{prefix}{new_seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.company_name or self.customer_name}"

class CustomerChangeLog(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.CASCADE, related_name='change_logs')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField()

    class Meta:
        ordering = ['-timestamp']
