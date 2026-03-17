from django.contrib import admin
from .models import Quotation, QuotationItem, Invoice, InvoiceItem, Return

class QuotationItemInline(admin.TabularInline):
    model = QuotationItem
    extra = 1

@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ('quotation_number', 'customer', 'salesperson', 'creation_date', 'valid_until', 'total_amount')
    list_filter = ('creation_date', 'salesperson')
    search_fields = ('quotation_number', 'customer__customer_name', 'customer__company_name')
    inlines = [QuotationItemInline]

class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 1

@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ('invoice_number', 'invoice_type', 'customer', 'status', 'total_amount', 'creation_date')
    list_filter = ('status', 'invoice_type', 'salesperson')
    search_fields = ('invoice_number', 'customer__customer_name', 'customer__company_name')
    inlines = [InvoiceItemInline]

@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ('return_number', 'original_invoice', 'returned_product', 'quantity', 'reason', 'condition', 'credit_note_issued')
    list_filter = ('reason', 'condition', 'credit_note_issued', 'stock_updated')
    search_fields = ('return_number', 'original_invoice__invoice_number')
