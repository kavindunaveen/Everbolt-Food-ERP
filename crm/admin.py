from django.contrib import admin
from .models import Customer, CustomerDeliveryAddress

class DeliveryAddressInline(admin.TabularInline):
    model = CustomerDeliveryAddress
    extra = 0
    fields = ('label', 'line1', 'line2', 'city', 'province', 'zip_code', 'is_default')

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_code', 'customer_name', 'company_name', 'phone', 'customer_type', 'assigned_sales_officer')
    list_filter = ('customer_type', 'payment_terms', 'assigned_sales_officer')
    search_fields = ('customer_code', 'customer_name', 'company_name', 'phone')
    inlines = [DeliveryAddressInline]

@admin.register(CustomerDeliveryAddress)
class CustomerDeliveryAddressAdmin(admin.ModelAdmin):
    list_display = ('customer', 'label', 'city', 'is_default')
    list_filter = ('is_default',)
    search_fields = ('customer__customer_name', 'customer__company_name', 'label', 'city')
