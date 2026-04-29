from django import forms
from .models import WebsiteSettings, WebsiteCategory, WebsiteProduct, WebsitePage, WebsiteEnquiry
from inventory.models import Product


class WebsiteSettingsForm(forms.ModelForm):
    class Meta:
        model = WebsiteSettings
        exclude = ['updated_at']
        widgets = {
            'site_name': forms.TextInput(attrs={'placeholder': 'e.g. Organic Foods Lanka'}),
            'tagline': forms.TextInput(attrs={'placeholder': 'e.g. Pure. Natural. Sri Lankan.'}),
            'hero_title': forms.TextInput(attrs={'placeholder': 'e.g. Fresh From Sri Lanka'}),
            'hero_subtitle': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Hero section description...'}),
            'contact_email': forms.EmailInput(attrs={'placeholder': 'info@organicfoodslanka.com'}),
            'contact_phone': forms.TextInput(attrs={'placeholder': '+94 77 123 4567'}),
            'contact_address': forms.Textarea(attrs={'rows': 3}),
            'facebook_url': forms.URLInput(attrs={'placeholder': 'https://facebook.com/...'}),
            'instagram_url': forms.URLInput(attrs={'placeholder': 'https://instagram.com/...'}),
            'whatsapp_number': forms.TextInput(attrs={'placeholder': '94771234567'}),
            'maintenance_message': forms.Textarea(attrs={'rows': 3}),
        }


class WebsiteCategoryForm(forms.ModelForm):
    class Meta:
        model = WebsiteCategory
        fields = ['name', 'slug', 'description', 'display_order', 'is_visible']
        widgets = {
            'name': forms.TextInput(attrs={'placeholder': 'e.g. Spices'}),
            'slug': forms.TextInput(attrs={'placeholder': 'auto-generated if blank'}),
            'description': forms.Textarea(attrs={'rows': 3}),
        }


class WebsiteProductForm(forms.ModelForm):
    class Meta:
        model = WebsiteProduct
        fields = [
            'inventory_product', 'website_category', 'display_name',
            'short_description', 'description', 'slug',
            'status', 'display_order', 'is_featured', 'show_stock', 'min_order_qty'
        ]
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Leave blank to use inventory product name'}),
            'short_description': forms.TextInput(attrs={'placeholder': 'Short one-liner shown in product cards'}),
            'description': forms.Textarea(attrs={'rows': 5, 'placeholder': 'Full product description for the website...'}),
            'slug': forms.TextInput(attrs={'placeholder': 'auto-generated if blank'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # For edit forms, show all products; for create, show only unlisted
        if not self.instance.pk:
            listed_ids = WebsiteProduct.objects.values_list('inventory_product_id', flat=True)
            self.fields['inventory_product'].queryset = Product.objects.exclude(pk__in=listed_ids).order_by('category', 'name')
        else:
            self.fields['inventory_product'].queryset = Product.objects.order_by('category', 'name')
        self.fields['inventory_product'].widget.attrs['class'] = 'no-select2'


class WebsitePageForm(forms.ModelForm):
    class Meta:
        model = WebsitePage
        fields = ['title', 'slug', 'content', 'meta_description', 'status', 'show_in_nav', 'nav_label', 'display_order']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'Page title'}),
            'slug': forms.TextInput(attrs={'placeholder': 'e.g. about-us'}),
            'content': forms.Textarea(attrs={'rows': 15, 'placeholder': 'Page content (HTML supported)...'}),
            'meta_description': forms.TextInput(attrs={'placeholder': 'SEO description (max 300 chars)'}),
            'nav_label': forms.TextInput(attrs={'placeholder': 'Label shown in navigation'}),
        }


class WebsiteEnquiryNotesForm(forms.ModelForm):
    class Meta:
        model = WebsiteEnquiry
        fields = ['status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Internal notes about this enquiry...'}),
        }
