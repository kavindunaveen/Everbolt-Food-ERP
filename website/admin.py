from django.contrib import admin
from .models import WebsiteBlogPost

@admin.register(WebsiteBlogPost)
class WebsiteBlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'published_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
