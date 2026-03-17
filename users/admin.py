from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User

@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'is_staff_status')
    list_filter = ('role', 'is_active')
    
    fieldsets = UserAdmin.fieldsets + (
        ('Sales Data', {'fields': ('role', 'contact_number', 'assigned_area')}),
    )

    def is_staff_status(self, obj):
        return obj.is_staff
    is_staff_status.boolean = True
    is_staff_status.short_description = 'Staff Status'
