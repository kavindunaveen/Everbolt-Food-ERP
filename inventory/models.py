from django.db import models
from django.conf import settings

class Brand(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    
    def __str__(self):
        return self.name

class Product(models.Model):
    class UnitTypes(models.TextChoices):
        PCS = 'PCS', 'pcs'
        BOX = 'BOX', 'box'
        PACK = 'PACK', 'pack'
        KG = 'KG', 'kg'
        G = 'G', 'g'
        L = 'L', 'l'
        ML = 'ML', 'ml'

    class ProductTypes(models.TextChoices):
        MANUFACTURED = 'MANUFACTURED', 'Manufactured'
        REPACKED = 'REPACKED', 'Repacked'
        BLENDED = 'BLENDED', 'Blended'
        TRADING = 'TRADING', 'Trading'
        CONTRACTED = 'CONTRACTED', 'Contract Packed'

    class InventoryClasses(models.TextChoices):
        RAW = 'RAW', 'Raw Material'
        PACKAGING = 'PACKAGING', 'Packaging Material'
        FINISHED = 'FINISHED', 'Finished Good'
        SEMI_FINISHED = 'SEMI_FINISHED', 'Semi-Finished Good'
        CONSUMABLE = 'CONSUMABLE', 'Consumable'

    product_id = models.CharField(max_length=50, unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    packet_size = models.CharField(max_length=100, blank=True, null=True)
    stock_unit = models.CharField(max_length=20, choices=UnitTypes.choices, default=UnitTypes.PCS)
    selling_unit = models.CharField(max_length=20, choices=UnitTypes.choices, default=UnitTypes.PCS)
    
    inventory_class = models.CharField(max_length=50, choices=InventoryClasses.choices, default=InventoryClasses.FINISHED)
    product_type = models.CharField(max_length=50, choices=ProductTypes.choices, default=ProductTypes.MANUFACTURED)
    
    track_stock = models.BooleanField(default=True)
    allow_negative_stock = models.BooleanField(default=False)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    custom_load_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    special_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00) # Fixed 18% generic tax
    
    status = models.BooleanField(default=True, help_text="True if active")
    
    # This is a cache field derived from StockLedger, it should not be manually maintained.
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0.000, help_text="Cached balance from StockLedger")

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        
        is_new_id = False
        # Generate Product ID if not exists or if it's a temporary one
        if not self.product_id or self.product_id.startswith('PRD_'):
            prefix = 'EFPR'
            if self.category and self.category.name:
                cat_name = self.category.name.upper()
                CATEGORY_PREFIX_MAP = {
                    'SPICES': 'EFSP',
                    'HERBAL TEA': 'EFHT',
                    'FLAVORED TEA': 'EFFT',
                    'TEA': 'EFST',
                    'KITHUL': 'EFKT',
                    'CONFECTIONARIES': 'EFCP',
                }
                prefix = CATEGORY_PREFIX_MAP.get(cat_name, f"EF{cat_name[:2].upper()}")
            
            # Find the last sequence for this prefix
            last_product = Product.objects.filter(product_id__startswith=f"{prefix}-").order_by('-product_id').first()
            if last_product and '-' in last_product.product_id:
                try:
                    last_seq = int(last_product.product_id.split('-')[1])
                    next_seq = last_seq + 1
                except ValueError:
                    next_seq = 1
            else:
                next_seq = 1
                
            self.product_id = f"{prefix}-{next_seq:04d}"
            is_new_id = True
            
        # Generate SKU if not exists or if we originated a temp ID earlier (so we also fix the old SKUs)
        if not self.sku or '_' in self.sku or is_new_id:
            base_sku = slugify(self.name).upper()
            if self.packet_size:
                packet_slug = slugify(self.packet_size).upper()
                if not base_sku.endswith(packet_slug) and packet_slug not in base_sku:
                    base_sku += f"-{packet_slug}"
                
            sku = base_sku
            counter = 1
            while Product.objects.filter(sku=sku).exclude(pk=self.pk).exists():
                sku = f"{base_sku}-{counter}"
                counter += 1
            self.sku = sku
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.sku}] {self.name}"

class StockLedger(models.Model):
    class TransactionTypes(models.TextChoices):
        OPENING = 'OPENING', 'Opening Stock'
        GRN = 'GRN', 'GRN'
        PROD_CONS = 'PROD_CONS', 'Production Consumption'
        PROD_OUT = 'PROD_OUT', 'Production Output'
        SALES_ISS = 'SALES_ISS', 'Sales Issue'
        SALES_RET = 'SALES_RET', 'Sales Return'
        PURC_RET = 'PURC_RET', 'Purchase Return'
        ADJ_POS = 'ADJ_POS', 'Stock Adjustment Positive'
        ADJ_NEG = 'ADJ_NEG', 'Stock Adjustment Negative'

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='ledger_entries')
    date = models.DateTimeField(auto_now_add=True)
    tx_type = models.CharField(max_length=20, choices=TransactionTypes.choices)
    qty_in = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    qty_out = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    reference_type = models.CharField(max_length=50) # e.g. 'GRN', 'PROD', 'INV', 'SYS'
    reference_id = models.IntegerField(null=True, blank=True)
    reference_number = models.CharField(max_length=100)
    remarks = models.CharField(max_length=255, blank=True, null=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} | {self.tx_type} | IN: {self.qty_in} | OUT: {self.qty_out}"

class StockAdjustment(models.Model):
    class AdjustmentTypes(models.TextChoices):
        POSITIVE = 'POSITIVE', 'Positive Adjustment'
        NEGATIVE = 'NEGATIVE', 'Negative Adjustment'

    class StatusChoices(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        CONFIRMED = 'CONFIRMED', 'Confirmed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    adjustment_number = models.CharField(max_length=50, unique=True, blank=True)
    date = models.DateField()
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    adjustment_type = models.CharField(max_length=20, choices=AdjustmentTypes.choices)
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    reason = models.CharField(max_length=255)
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=StatusChoices.choices, default=StatusChoices.DRAFT)
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.adjustment_number:
            last_adj = StockAdjustment.objects.order_by('-id').first()
            if last_adj and last_adj.adjustment_number.startswith('ADJ-'):
                try:
                    seq = int(last_adj.adjustment_number.split('-')[1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.adjustment_number = f"ADJ-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.adjustment_number} - {self.product.name}"
