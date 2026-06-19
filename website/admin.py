from django.contrib import admin
from .models import WebsiteCategory, WebsiteProduct, WebsiteEnquiry, WebsitePage, WebsiteSettings, WebsiteOrder, WebsiteOrderItem, WebsiteBlogPost, WebsiteHeroSlide

admin.site.register(WebsiteCategory)
admin.site.register(WebsiteProduct)
admin.site.register(WebsiteEnquiry)
admin.site.register(WebsitePage)
admin.site.register(WebsiteSettings)
admin.site.register(WebsiteOrder)
admin.site.register(WebsiteOrderItem)
admin.site.register(WebsiteHeroSlide)

@admin.register(WebsiteBlogPost)
class WebsiteBlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'status', 'published_at', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('title', 'content')
    prepopulated_fields = {'slug': ('title',)}
