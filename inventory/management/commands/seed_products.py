from django.core.management.base import BaseCommand
from inventory.models import Product, Category, Brand

class Command(BaseCommand):
    help = 'Seeds the database with 5 sample products according to SRS'

    def handle(self, *args, **kwargs):
        # Create Sample Brands
        everbolt, _ = Brand.objects.get_or_create(name='Everbolt')
        everleaf, _ = Brand.objects.get_or_create(name='Everleaf')

        # Create Sample Categories
        confectionery, _ = Category.objects.get_or_create(name='Confectionery')
        spices, _ = Category.objects.get_or_create(name='Spices')
        herbal_tea, _ = Category.objects.get_or_create(name='Herbal Tea')

        # Create 5 Sample Products
        products = [
            {
                'sku': 'EVB-CONF-001',
                'product_id': 'P-001',
                'name': 'Everbolt Chocolate Pack',
                'brand': everbolt,
                'category': confectionery,
                'selling_unit': Product.UnitTypes.PACK,
                'product_type': Product.ProductTypes.MANUFACTURED,
                'selling_price': 500.00,
                'current_stock': 150
            },
            {
                'sku': 'EVB-SPIC-002',
                'product_id': 'P-002',
                'name': 'Everbolt Cinnamon 500g',
                'brand': everbolt,
                'category': spices,
                'selling_unit': Product.UnitTypes.KG,
                'product_type': Product.ProductTypes.REPACKED,
                'selling_price': 1200.00,
                'current_stock': 50
            },
            {
                'sku': 'EVL-TEA-003',
                'product_id': 'P-003',
                'name': 'Everleaf Green Tea Box',
                'brand': everleaf,
                'category': herbal_tea,
                'selling_unit': Product.UnitTypes.BOX,
                'product_type': Product.ProductTypes.BLENDED,
                'selling_price': 850.00,
                'current_stock': 200
            },
            {
                'sku': 'EVL-TEA-004',
                'product_id': 'P-004',
                'name': 'Everleaf Black Tea Loose',
                'brand': everleaf,
                'category': herbal_tea,
                'selling_unit': Product.UnitTypes.KG,
                'product_type': Product.ProductTypes.BLENDED,
                'selling_price': 1500.00,
                'current_stock': 80
            },
            {
                'sku': 'EVB-CONF-005',
                'product_id': 'P-005',
                'name': 'Everbolt Assorted Sweets',
                'brand': everbolt,
                'category': confectionery,
                'selling_unit': Product.UnitTypes.BOX,
                'product_type': Product.ProductTypes.TRADING,
                'selling_price': 2200.00,
                'current_stock': 30
            }
        ]

        for p_data in products:
            product, created = Product.objects.get_or_create(sku=p_data['sku'], defaults=p_data)
            status = "Created" if created else "Already exists"
            self.stdout.write(self.style.SUCCESS(f'{status} product: {product.name} ({product.sku})'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded 5 sample products.'))
