from django.db import models, transaction
from django.core.validators import RegexValidator

class SupplierType(models.TextChoices):
    SUGAR = 'SUGAR', 'Sugar'
    RAW_MATERIAL = 'RAW_MATERIAL', 'Raw material supplier'
    TEA_RAW = 'TEA_RAW', 'Tea raw supplier'
    PRINTING_SERVICE = 'PRINTING_SERVICE', 'Printing service supplier'
    PACKING_SERVICE = 'PACKING_SERVICE', 'Packing service supplier'
    DRIED_RAW = 'DRIED_RAW', 'Dried raw material supplier'
    SPICES_RAW = 'SPICES_RAW', 'Spices raw material supplier'
    KITHUL = 'KITHUL', 'Kithul supplier'
    HERBS_RAW = 'HERBS_RAW', 'Herbs raw material supplier'
    TRADING_ITEM = 'TRADING_ITEM', 'Trading item supplier'
    OTHER = 'OTHER', 'Other'

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

class SLBankChoices(models.TextChoices):
    BOC = 'BOC', 'Bank of Ceylon (BOC)'
    PEOPLES = 'PEOPLES', "People's Bank"
    COMMERCIAL = 'COMMERCIAL', 'Commercial Bank of Ceylon PLC'
    HNB = 'HNB', 'Hatton National Bank PLC (HNB)'
    SAMPATH = 'SAMPATH', 'Sampath Bank PLC'
    SEYLAN = 'SEYLAN', 'Seylan Bank PLC'
    NTB = 'NTB', 'Nations Trust Bank PLC (NTB)'
    NDB = 'NDB', 'National Development Bank PLC (NDB)'
    DFCC = 'DFCC', 'DFCC Bank PLC'
    PAN_ASIA = 'PAN_ASIA', 'Pan Asia Banking Corporation PLC'
    UNION = 'UNION', 'Union Bank of Colombo PLC'
    STANDARD_CHARTERED = 'STANDARD_CHARTERED', 'Standard Chartered Bank'
    HSBC = 'HSBC', 'HSBC'
    AMANA = 'AMANA', 'Amana Bank'
    CARGILLS = 'CARGILLS', 'Cargills Bank'

class Supplier(models.Model):
    supplier_code = models.CharField(max_length=50, unique=True, blank=True)
    supplier_name = models.CharField(max_length=200)
    
    supplier_type = models.CharField(max_length=50, choices=SupplierType.choices)
    custom_supplier_type = models.CharField(max_length=150, blank=True, null=True, help_text="Specify if type is Other")
    
    address_line1 = models.CharField(max_length=255)
    address_line2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100)
    province = models.CharField(max_length=100, choices=ProvinceChoices.choices)
    zip_code = models.CharField(max_length=20, blank=True, null=True)
    
    # Contact number with numbers only validation
    contact_number = models.CharField(
        max_length=20, 
        validators=[RegexValidator(regex=r'^\d+$', message='Contact number must contain only digits.')]
    )
    
    email = models.EmailField(blank=True, null=True)
    
    # Bank details
    bank_name = models.CharField(max_length=50, choices=SLBankChoices.choices, blank=True, null=True)
    bank_branch = models.CharField(max_length=150, blank=True, null=True)
    bank_account_no = models.CharField(max_length=100, blank=True, null=True)
    
    vat_reg_num = models.CharField(max_length=50, blank=True, null=True, verbose_name="VAT Registration Number", help_text="Enter valid VAT number")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.supplier_code:
            prefix = "SUP"
            with transaction.atomic():
                last_supplier = Supplier.objects.select_for_update().filter(supplier_code__startswith=prefix).order_by('-supplier_code').first()
                if last_supplier:
                    try:
                        last_seq = int(last_supplier.supplier_code.replace(prefix, ""))
                        new_seq = last_seq + 1
                    except ValueError:
                        new_seq = 1
                else:
                    new_seq = 1
                self.supplier_code = f"{prefix}{new_seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.supplier_code} - {self.supplier_name}"
