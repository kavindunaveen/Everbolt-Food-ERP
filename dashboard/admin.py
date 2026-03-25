from django.contrib import admin
from .models import SalesTarget

@admin.register(SalesTarget)
class SalesTargetAdmin(admin.ModelAdmin):
    list_display = ('year', 'target_type', 'category', 'target_value')
    list_filter = ('year', 'target_type', 'category')
    search_fields = ('year', 'target_value')
