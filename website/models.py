from django.db import models
from django.utils.text import slugify
from inventory.models import Product


class WebsiteSettings(models.Model):
    """Global settings for the public website."""
    site_name = models.CharField(max_length=100, default='Organic Foods Lanka')
    tagline = models.CharField(max_length=200, blank=True)
    hero_title = models.CharField(max_length=200, blank=True)
    hero_subtitle = models.TextField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=30, blank=True)
    contact_address = models.TextField(blank=True)
    facebook_url = models.URLField(blank=True)
    instagram_url = models.URLField(blank=True)
    whatsapp_number = models.CharField(max_length=20, blank=True)
    is_maintenance_mode = models.BooleanField(default=False)
    maintenance_message = models.TextField(blank=True, default='We are currently performing maintenance. We\'ll be back soon!')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Website Settings'
        verbose_name_plural = 'Website Settings'

    def __str__(self):
        return f'Website Settings — {self.site_name}'

    def save(self, *args, **kwargs):
        # Ensure singleton
        self.__class__.objects.exclude(pk=self.pk).delete()
        super().save(*args, **kwargs)

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class WebsiteCategory(models.Model):
    """Product categories shown on the website shop."""
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    display_order = models.PositiveIntegerField(default=0)
    is_visible = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']
        verbose_name = 'Website Category'
        verbose_name_plural = 'Website Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)


class WebsiteProduct(models.Model):
    """A product listed on the public website, linked to an inventory product."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'
        HIDDEN = 'HIDDEN', 'Hidden'

    inventory_product = models.OneToOneField(
        Product, on_delete=models.CASCADE,
        related_name='website_listing',
        help_text='The inventory product this listing is linked to.'
    )
    website_category = models.ForeignKey(
        WebsiteCategory, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='products'
    )
    display_name = models.CharField(max_length=200, blank=True, help_text='Override name on website (leave blank to use product name)')
    description = models.TextField(blank=True, help_text='Public-facing product description for the website')
    short_description = models.CharField(max_length=300, blank=True)
    slug = models.SlugField(unique=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    display_order = models.PositiveIntegerField(default=0)
    is_featured = models.BooleanField(default=False, help_text='Show in featured/hero section')
    show_stock = models.BooleanField(default=False, help_text='Show live stock count to customers')
    min_order_qty = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'display_name']
        verbose_name = 'Website Product'
        verbose_name_plural = 'Website Products'

    def __str__(self):
        return self.get_display_name()

    def get_display_name(self):
        return self.display_name or self.inventory_product.name

    def get_price(self):
        """Returns MRP = selling_price × 1.18."""
        return round(self.inventory_product.selling_price * 1.18, 2)

    def get_ex_vat_price(self):
        return self.inventory_product.selling_price

    def get_stock(self):
        return self.inventory_product.current_stock

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.get_display_name())
            self.slug = base_slug
        super().save(*args, **kwargs)


class WebsitePage(models.Model):
    """Static/CMS pages for the website (About, Contact, etc.)."""

    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PUBLISHED = 'PUBLISHED', 'Published'

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField(help_text='Main page content (HTML supported)')
    meta_description = models.CharField(max_length=300, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    show_in_nav = models.BooleanField(default=False)
    nav_label = models.CharField(max_length=60, blank=True)
    display_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['display_order', 'title']
        verbose_name = 'Website Page'
        verbose_name_plural = 'Website Pages'

    def __str__(self):
        return self.title


class WebsiteEnquiry(models.Model):
    """Contact form submissions / enquiries from the website."""

    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESOLVED = 'RESOLVED', 'Resolved'
        SPAM = 'SPAM', 'Spam'

    name = models.CharField(max_length=150)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    notes = models.TextField(blank=True, help_text='Internal notes for this enquiry')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        verbose_name = 'Website Enquiry'
        verbose_name_plural = 'Website Enquiries'

    def __str__(self):
        return f'{self.name} — {self.subject or self.email} ({self.submitted_at.strftime("%d %b %Y")})'
