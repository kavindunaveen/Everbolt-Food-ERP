from django.db import models
from django.conf import settings
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


class ProductTargetGroup(models.Model):
    """A user-defined or automatic group of products that shares a single target (e.g. Sugar Sachets)."""
    name = models.CharField(max_length=100, unique=True, help_text="e.g. Sugar Sachets, Nescafe")
    products = models.ManyToManyField(Product, related_name='target_groups')
    display_order = models.IntegerField(default=0)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'added_at']

    def __str__(self):
        return self.name


class ProductTarget(models.Model):
    """Per-group sales target — yearly (month=None) or monthly (month=1..12)."""
    target_group = models.ForeignKey(
        ProductTargetGroup, on_delete=models.CASCADE, related_name='targets'
    )
    year = models.IntegerField()
    month = models.IntegerField(null=True, blank=True)
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = ('target_group', 'year', 'month')

    def __str__(self):
        import calendar as _cal
        period = _cal.month_abbr[self.month] if self.month else 'Yearly'
        return f"{self.target_group.name} | {self.year} | {period} | {self.target_value}"

class SalespersonTarget(models.Model):
    """Monthly sales target for a salesperson (Rs Ex-VAT)."""
    salesperson = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sales_targets'
    )
    year = models.IntegerField()
    month = models.IntegerField()
    target_value = models.DecimalField(max_digits=14, decimal_places=2, default=0)

    class Meta:
        unique_together = ('salesperson', 'year', 'month')

    def __str__(self):
        import calendar as _cal
        return f"{self.salesperson.username} | {self.year} {_cal.month_abbr[self.month]} | Rs {self.target_value}"

class ForecastingSettings(models.Model):
    """Settings for Advanced Analytics Forecasting (Monthly)."""
    year = models.IntegerField()
    month = models.IntegerField()
    milestone_target = models.DecimalField(max_digits=14, decimal_places=2, default=500000, help_text="e.g., 500000 for 500k milestones")
    total_working_days = models.IntegerField(default=25, help_text="Total working days in the month (e.g., excluding Sundays and Poya)")

    class Meta:
        unique_together = ('year', 'month')

    def __str__(self):
        import calendar as _cal
        return f"Forecasting Settings | {self.year} {_cal.month_abbr[self.month]}"
