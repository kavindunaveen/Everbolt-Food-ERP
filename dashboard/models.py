from django.db import models
from inventory.models import Product


class SalesTarget(models.Model):
    """Category-level targets (Overall / Sugar / Creamer / Tea) — drives top gauge KPI cards."""
    class TargetTypes(models.TextChoices):
        OVERALL_SALES = 'OVERALL_SALES', 'Overall Sales'
        CATEGORY_SALES = 'CATEGORY_SALES', 'Category Sales'
        CATEGORY_QTY = 'CATEGORY_QTY', 'Category Quantity'

    year = models.IntegerField(help_text="Year for the target (e.g., 2026)")
    month = models.IntegerField(
        null=True, blank=True,
        help_text="Leave blank for a yearly target. Set 1–12 for a specific month (1=Jan, 12=Dec)."
    )
    target_type = models.CharField(max_length=20, choices=TargetTypes.choices, default=TargetTypes.OVERALL_SALES)
    category = models.CharField(max_length=50, choices=Product.CategoryChoices.choices, null=True, blank=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2)

    class Meta:
        unique_together = ('year', 'month', 'target_type', 'category')

    def __str__(self):
        import calendar
        period = f"Month {self.month} ({calendar.month_abbr[self.month]})" if self.month else "Yearly"
        cat_str = f" - {self.category}" if self.category else ""
        return f"{self.year} | {period} | {self.get_target_type_display()}{cat_str} | {self.target_value}"


class TrackedProduct(models.Model):
    """Which products appear in the Product Targets grid and dashboard Product Performance section."""
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name='tracking'
    )
    display_order = models.IntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'added_at']

    def __str__(self):
        return f"Tracked: {self.product.name}"


class ProductTarget(models.Model):
    """Per-product sales target — yearly (month=None) or monthly (month=1..12)."""
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name='product_targets'
    )
    year = models.IntegerField()
    month = models.IntegerField(null=True, blank=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = ('product', 'year', 'month')

    def __str__(self):
        import calendar as _cal
        period = _cal.month_abbr[self.month] if self.month else 'Yearly'
        return f"{self.product.name} | {self.year} | {period} | {self.target_value}"

