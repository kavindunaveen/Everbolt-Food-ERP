from django.contrib import admin
from .models import Product

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('product_id', 'name', 'brand', 'category', 'current_stock', 'selling_price', 'status')
    list_filter = ('brand', 'category', 'status', 'product_type')
    search_fields = ('product_id', 'name')
    list_editable = ('current_stock', 'selling_price', 'status')
