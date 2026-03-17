from django.contrib import admin
from .models import Brand, Category, Product

@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    search_fields = ('name',)

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('sku', 'product_id', 'name', 'brand', 'category', 'current_stock', 'selling_price', 'status')
    list_filter = ('brand', 'category', 'status', 'product_type')
    search_fields = ('sku', 'product_id', 'name')
    list_editable = ('current_stock', 'selling_price', 'status')
