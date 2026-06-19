from django.db import migrations

def seed_hero_slides(apps, schema_editor):
    WebsiteHeroSlide = apps.get_model('website', 'WebsiteHeroSlide')
    
    slides_data = [
        {'title': 'Premium Ceylon Teas', 'image': 'website/hero/hero-tea-display.png', 'display_order': 1},
        {'title': 'Authentic Spices', 'image': 'website/hero/hero-organic.png', 'display_order': 2},
        {'title': 'Hotel Supplies', 'image': 'website/hero/main-bg.webp', 'display_order': 3},
    ]

    for slide in slides_data:
        WebsiteHeroSlide.objects.get_or_create(title=slide['title'], defaults=slide)

class Migration(migrations.Migration):

    dependencies = [
        ('website', '0007_websiteheroslide'),
    ]

    operations = [
        migrations.RunPython(seed_hero_slides),
    ]
