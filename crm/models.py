from django.db import models
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

class PaymentTerms(models.TextChoices):
    CASH = 'CASH', 'Cash'
    COD = 'COD', 'COD'
    CREDIT_15 = 'CREDIT_15', 'Credit - 15 days'
    CREDIT_30 = 'CREDIT_30', 'Credit - 30 days'
    CREDIT_45 = 'CREDIT_45', 'Credit - 45 days'
    CREDIT_60 = 'CREDIT_60', 'Credit - 60 days'

class Customer(models.Model):
    customer_code = models.CharField(max_length=50, unique=True)
    customer_name = models.CharField(max_length=200)
    company_name = models.CharField(max_length=200, blank=True, null=True)
    contact_person = models.CharField(max_length=150)
    phone = models.CharField(max_length=50)
    email = models.EmailField(blank=True, null=True)
    
    billing_address = models.TextField()
    delivery_address = models.TextField()
    
    customer_type = models.CharField(max_length=50, choices=CustomerType.choices)
    assigned_sales_officer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='customers')
    
    area_route = models.CharField(max_length=150)
    payment_terms = models.CharField(max_length=50, choices=PaymentTerms.choices, default=PaymentTerms.CASH)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    
    registration_date = models.DateField(auto_now_add=True)
    vat_enabled = models.BooleanField(default=True, help_text="Always compute 18% VAT")
    vat_number = models.CharField(max_length=50, blank=True, null=True)
    nic = models.CharField(max_length=20, blank=True, null=True)

    def __str__(self):
        return f"{self.company_name or self.customer_name}"

