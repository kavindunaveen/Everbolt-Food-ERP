import django.db.models.deletion
from django.db import migrations, models

def migrate_tracked_to_groups(apps, schema_editor):
    TrackedProduct = apps.get_model('dashboard', 'TrackedProduct')
    ProductTargetGroup = apps.get_model('dashboard', 'ProductTargetGroup')
    ProductTarget = apps.get_model('dashboard', 'ProductTarget')

    for tp in TrackedProduct.objects.all():
        group, created = ProductTargetGroup.objects.get_or_create(
            name=tp.product.name,
            defaults={'display_order': tp.display_order}
        )
        group.products.add(tp.product)
        
        ProductTarget.objects.filter(product=tp.product).update(target_group=group)

def rollback_groups_to_tracked(apps, schema_editor):
    TrackedProduct = apps.get_model('dashboard', 'TrackedProduct')
    ProductTargetGroup = apps.get_model('dashboard', 'ProductTargetGroup')
    ProductTarget = apps.get_model('dashboard', 'ProductTarget')

    for group in ProductTargetGroup.objects.all():
        product = group.products.first()
        if product:
            ProductTarget.objects.filter(target_group=group).update(product=product)

class Migration(migrations.Migration):

    dependencies = [
        ('dashboard', '0006_alter_producttarget_product_producttargetgroup_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_tracked_to_groups, rollback_groups_to_tracked),
    ]
