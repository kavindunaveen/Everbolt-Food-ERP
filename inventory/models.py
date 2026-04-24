from django.db import models
from django.conf import settings

class Product(models.Model):
    class BrandChoices(models.TextChoices):
        EVERBOLT = 'Everbolt', 'Everbolt'
        EVERLEAF = 'Everleaf', 'Everleaf'

    class CategoryChoices(models.TextChoices):
        CONFECTIONERY = 'Confectionery', 'Confectionery'
        DRIED_FRUITS = 'Dried Fruits', 'Dried Fruits'
        DRIED_VEGETABLES = 'Dried Vegetables', 'Dried Vegetables'
        SPICES = 'Spices', 'Spices'
        TEA = 'Tea', 'Tea'
        KITHUL = 'Kithul', 'Kithul'

    class TeaTypeChoices(models.TextChoices):
        HERBAL_TEA = 'Herbal Tea', 'Herbal Tea'
        ARTISAN_TEA = 'Artisan Tea', 'Artisan Tea'
        FLAVORED_TEA = 'Flavored Tea', 'Flavored Tea'
        BLACK_TEA = 'Black Tea', 'Black Tea'
        GREEN_TEA = 'Green Tea', 'Green Tea'
        CATERING_TEA = 'Catering Tea', 'Catering Tea'

    class UnitTypes(models.TextChoices):
        PCS = 'pcs', 'pcs'
        BOX = 'box', 'box'
        PACK = 'pack', 'pack'
        KG = 'Kg', 'Kg'
        G = 'g', 'g'
        ML = 'ml', 'ml'
        L = 'l', 'l'

    class ProductTypes(models.TextChoices):
        DIRECT_PACKING = 'Direct Packing', 'Direct Packing'
        BLENDED_TEA = 'Blended Tea Products', 'Blended Tea Products'
        CONFECTIONERY_PACKING = 'Confectionery Packing', 'Confectionery Packing'
        REPACKING = 'Repacking', 'Repacking'
        TRADING = 'Trading Products', 'Trading Products'

    class InventoryClasses(models.TextChoices):
        RAW = 'RAW', 'Raw Material'
        PACKAGING = 'PACKAGING', 'Packaging Material'
        FINISHED = 'FINISHED', 'Finished Good'
        SEMI_FINISHED = 'SEMI_FINISHED', 'Semi-Finished Good'
        CONSUMABLE = 'CONSUMABLE', 'Consumable'

    product_id = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=50, choices=BrandChoices.choices, default=BrandChoices.EVERBOLT)
    category = models.CharField(max_length=50, choices=CategoryChoices.choices, default=CategoryChoices.CONFECTIONERY)
    tea_type = models.CharField(max_length=50, choices=TeaTypeChoices.choices, blank=True, null=True)
    
    packet_size = models.CharField(max_length=100, blank=True, null=True)
    stock_unit = models.CharField(max_length=20, choices=UnitTypes.choices, default=UnitTypes.PCS)
    selling_unit = models.CharField(max_length=20, choices=UnitTypes.choices, default=UnitTypes.PCS)
    
    inventory_class = models.CharField(max_length=50, choices=InventoryClasses.choices, default=InventoryClasses.FINISHED)
    product_type = models.CharField(max_length=50, choices=ProductTypes.choices, default=ProductTypes.DIRECT_PACKING, verbose_name="Production Type")
    
    track_stock = models.BooleanField(default=True)
    allow_negative_stock = models.BooleanField(default=False)
    reorder_level = models.DecimalField(max_digits=12, decimal_places=3, default=0.000)
    
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    price_tier_100 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Price for <= 100 pcs")
    price_tier_250 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Price for <= 250 pcs")
    price_tier_500 = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True, help_text="Price for >= 500 pcs")
    custom_load_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00) # Fixed 18% generic tax
    
    status = models.BooleanField(default=True, help_text="True if active")
    
    # This is a cache field derived from StockLedger, it should not be manually maintained.
    current_stock = models.DecimalField(max_digits=12, decimal_places=3, default=0.000, help_text="Cached balance from StockLedger")

    @property
    def available_stock(self):
        """Returns current stock minus active reserves."""
        from django.utils import timezone
        active_reserves = self.reserves.filter(expiry_time__gt=timezone.now()).aggregate(models.Sum('quantity'))['quantity__sum'] or 0
        return self.current_stock - active_reserves

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        
        # Generate Product ID if not exists or if it's a temporary one
        if not self.product_id or self.product_id.startswith('PRD_'):
            prefix = 'EF'
            if self.category:
                cat_name = self.category.upper()
                CATEGORY_PREFIX_MAP = {
                    'SPICES': 'EFSP',
                    'TEA': 'EFTE',
                    'KITHUL': 'EFKT',
                    'CONFECTIONERY': 'EFCN',
                    'DRIED FRUITS': 'EFDF',
                    'DRIED VEGETABLES': 'EFDV',
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
            
        super().save(*args, **kwargs)

    def __str__(self):
        return f"[{self.product_id}] {self.name}"

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
                    seq = int(last_adj.adjustment_number.split('-')[-1]) + 1
                except ValueError:
                    seq = 1
            else:
                seq = 1
            self.adjustment_number = f"ADJ-{seq:04d}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.adjustment_number} - {self.product.name}"

class StockReserve(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reserves')
    quantity = models.DecimalField(max_digits=12, decimal_places=3)
    # reference to what is holding the stock
    reference_type = models.CharField(max_length=50) # e.g. 'INV'
    reference_id = models.IntegerField()
    expiry_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def is_valid(self):
        from django.utils import timezone
        return self.expiry_time > timezone.now()

    def __str__(self):
        return f"Reserve {self.quantity} for {self.product.name}"
