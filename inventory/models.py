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

    product_id = models.CharField(max_length=50, unique=True)
    sku = models.CharField(max_length=50, unique=True)
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

    def __str__(self):
        return f"[{self.sku}] {self.name}"

