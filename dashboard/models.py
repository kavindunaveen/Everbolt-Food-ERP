from django.db import models
from inventory.models import Product

class SalesTarget(models.Model):
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
    category = models.CharField(max_length=50, choices=Product.CategoryChoices.choices, null=True, blank=True, help_text="Select a category if target type is Category Sales or Category Qty")
    target_value = models.DecimalField(max_digits=14, decimal_places=2, help_text="Target value")

    class Meta:
        unique_together = ('year', 'month', 'target_type', 'category')

    def __str__(self):
        import calendar
        period = f"Month {self.month} ({calendar.month_abbr[self.month]})" if self.month else "Yearly"
        cat_str = f" - {self.category}" if self.category else ""
        return f"{self.year} | {period} | {self.get_target_type_display()}{cat_str} | {self.target_value}"
