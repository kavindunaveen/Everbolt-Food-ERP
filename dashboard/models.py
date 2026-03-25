from django.db import models
from inventory.models import Category

class SalesTarget(models.Model):
    class TargetTypes(models.TextChoices):
        OVERALL_SALES = 'OVERALL_SALES', 'Overall Sales'
        CATEGORY_SALES = 'CATEGORY_SALES', 'Category Sales'
        CATEGORY_QTY = 'CATEGORY_QTY', 'Category Quantity'

    year = models.IntegerField(help_text="Year for the target (e.g., 2026)")
    target_type = models.CharField(max_length=20, choices=TargetTypes.choices, default=TargetTypes.OVERALL_SALES)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, help_text="Select a category if target type is Category Sales or Category Qty")
    target_value = models.DecimalField(max_digits=14, decimal_places=2, help_text="Yearly target value")

    class Meta:
        unique_together = ('year', 'target_type', 'category')

    def __str__(self):
        cat_str = f" - {self.category.name}" if self.category else ""
        return f"{self.year} | {self.get_target_type_display()}{cat_str} | {self.target_value}"
