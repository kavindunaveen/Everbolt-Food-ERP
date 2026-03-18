from django.db import models

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

    class ProductTypes(models.TextChoices):
        MANUFACTURED = 'MANUFACTURED', 'Manufactured'
        BLENDED = 'BLENDED', 'Blended'
        REPACKED = 'REPACKED', 'Repacked'
        CONTRACTED = 'CONTRACTED', 'Contracted Packing'
        TRADING = 'TRADING', 'Trading'

    product_id = models.CharField(max_length=50, unique=True, blank=True)
    sku = models.CharField(max_length=50, unique=True, blank=True)
    name = models.CharField(max_length=200)
    brand = models.ForeignKey(Brand, on_delete=models.SET_NULL, null=True, blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True)
    
    packet_size = models.CharField(max_length=100, blank=True, null=True)
    selling_unit = models.CharField(max_length=20, choices=UnitTypes.choices, default=UnitTypes.PCS)
    product_type = models.CharField(max_length=50, choices=ProductTypes.choices, default=ProductTypes.MANUFACTURED)
    
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    custom_load_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    special_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=18.00) # Fixed 18% generic tax
    
    status = models.BooleanField(default=True, help_text="True if active/in stock")
    current_stock = models.IntegerField(default=0)

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

