from django.contrib import admin
from .models import ISOCategory, ISOCriteria, ISODailyPlan, ISODailyTask

@admin.register(ISOCategory)
class ISOCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name',)

@admin.register(ISOCriteria)
class ISOCriteriaAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'duration_type', 'created_by', 'created_at')
    list_filter = ('duration_type', 'category')
    search_fields = ('name',)

class ISODailyTaskInline(admin.TabularInline):
    model = ISODailyTask
    extra = 0
    readonly_fields = ('task_description', 'is_checked', 'remark')
    can_delete = False

@admin.register(ISODailyPlan)
class ISODailyPlanAdmin(admin.ModelAdmin):
    list_display = ('criteria', 'date', 'submitted_by', 'submitted_at')
    list_filter = ('date', 'criteria')
    search_fields = ('criteria__name', 'submitted_by__username')
    inlines = [ISODailyTaskInline]
    date_hierarchy = 'date'
