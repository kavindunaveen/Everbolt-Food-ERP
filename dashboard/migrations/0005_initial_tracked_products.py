"""
Data migration: find the initial tracked products by name keywords and register them.
Uses name-based matching only — no hardcoded product IDs.
Skips any keyword where no matching product is found in the live DB.
"""
from django.db import migrations

# Keywords to match against product names (case-insensitive).
# Each tuple: (keyword, display_order)
INITIAL_KEYWORDS = [
    ('sugar sachet', 0),
    ('creamer',      1),
    ('black tea',    2),
    ('green tea',    3),
    ('catering tea', 4),
    ('nescafe',      5),
    ('coffee mate',  6),
    ('salt',         7),
]


def add_tracked_products(apps, schema_editor):
    Product = apps.get_model('inventory', 'Product')
    TrackedProduct = apps.get_model('dashboard', 'TrackedProduct')

    already_tracked_ids = set(
        TrackedProduct.objects.values_list('product_id', flat=True)
    )

    for keyword, order in INITIAL_KEYWORDS:
        # Find first active finished-good product whose name contains the keyword
        product = (
            Product.objects
            .filter(name__icontains=keyword, status=True)
            .exclude(id__in=already_tracked_ids)
            .first()
        )
        if product:
            TrackedProduct.objects.get_or_create(
                product=product,
                defaults={'display_order': order}
            )
            already_tracked_ids.add(product.id)


def remove_tracked_products(apps, schema_editor):
    """Reverse: remove all TrackedProduct rows (no data is deleted from ProductTarget
    because the reverse migration drops the table anyway)."""
    TrackedProduct = apps.get_model('dashboard', 'TrackedProduct')
    TrackedProduct.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0004_trackedproduct_producttarget'),
        ('inventory', '0006_stockadjustment'),
    ]

    operations = [
        migrations.RunPython(add_tracked_products, remove_tracked_products),
    ]
