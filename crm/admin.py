from django.contrib import admin
from .models import Customer

@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ('customer_code', 'customer_name', 'company_name', 'phone', 'customer_type', 'assigned_sales_officer')
    list_filter = ('customer_type', 'payment_terms', 'assigned_sales_officer')
    search_fields = ('customer_code', 'customer_name', 'company_name', 'phone')
