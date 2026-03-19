from django.core.management.base import BaseCommand
from inventory.models import Category, Product


PRODUCTS_DATA = [
    {
        'category': 'SPICES',
        'items': [
            ('Chillie Powder 1kg',           1390.00),
            ('Chillie Powder 500g',           705.00),
            ('Chillie Powder 200g',           285.00),
            ('Chillie Powder 100g',           150.00),
            ('Chillie Pieces 1kg',           1465.00),
            ('Chillie Pieces 500g',           735.00),
            ('Chillie Pieces 200g',           300.00),
            ('Chillie Pieces 100g',           155.00),
            ('Curry Powder 1kg',             1675.00),
            ('Curry Powder 500g',             845.00),
            ('Curry Powder 200g',             340.00),
            ('Curry Powder 100g',             175.00),
            ('Roasted Curry Powder 1kg',     1810.00),
            ('Roasted Curry Powder 500g',     910.00),
            ('Roasted Curry Powder 200g',     370.00),
            ('Roasted Curry Powder 100g',     190.00),
            ('Turmeric Powder 1kg',          3890.00),
            ('Turmeric Powder 500g',         1950.00),
            ('Turmeric Powder 200g',          785.00),
            ('Turmeric Powder 100g',          395.00),
            ('Pepper Powder 1kg',            3130.00),
            ('Pepper Powder 500g',           1570.00),
            ('Pepper Powder 200g',            630.00),
            ('Pepper Powder 100g',            320.00),
        ],
    },
    {
        'category': 'HERBAL TEA',
        'items': [
            ('Ushma',              1150.00),
            ('Slim Herb',         1060.00),
            ('Island Spicy Fusion', 1100.00),
            ('Special Hibiscus',  1175.00),
            ('Herbal Soothe',     1050.00),
            ('Harmony Brew',      1290.00),
            ('Fat Burn',          1150.00),
            ('Detox',             1060.00),
            ('Citrus',            1050.00),
            ('Calm Mind',         1230.00),
            ('Balance Blend',     1230.00),
            ('Moringa Morning',   1000.00),
            ('Immuno Up',         1100.00),
            ('Glyco Guard',        900.00),
            ('Green Guard',       1050.00),
            ('Vita Cure',         1050.00),
        ],
    },
    {
        'category': 'FLAVORED TEA',
        'items': [
            ('Jasmine Flavored Tea',          950.00),
            ('Mango Flavored Tea',            530.00),
            ('Ginger Flavored Tea',           565.00),
            ('Caramel Flavored Tea',          565.00),
            ('Lemon Green Tea Flavored Tea',  575.00),
            ('Pineapple Flavored Tea',        560.00),
            ('Strawberry Flavored Tea',       530.00),
            ('Passion Fruit Flavored Tea',    560.00),
            ('Green Tea Box',                 565.00),
            ('Black Tea Box',                 530.00),
        ],
    },
    {
        'category': 'TEA',
        'items': [
            ('Everleaf Artisan Green Tea 50g',      1790.00),
            ('Everleaf Artisan Green Tea 100g',     2550.00),
            ('Everleaf Artisan Black Tea 50g',      1790.00),
            ('Everleaf Artisan Black Tea 100g',     2550.00),
            ('Everleaf Artisan White Tea 50g',      1790.00),
            ('Everleaf Artisan White Tea 100g',     2550.00),
            ('Everleaf Artisan Wangedi Pakoe 50g',  1350.00),
            ('Everleaf Artisan Wangedi Pakoe 100g', 1750.00),
        ],
    },
    {
        'category': 'KITHUL',
        'items': [
            ('Kithul Treacle 375ml',  1800.00),
            ('Kithul Powder 200g',    1000.00),
            ('Kithul Flour 200g',      590.00),
            ('Kithul Pieces 200g',     850.00),
            ('Kithul Jaggery 300g',   2100.00),
        ],
    },
    {
        'category': 'CONFECTIONARIES',
        'items': [
            ('White Sugar Sachet 5g',     4.50),
            ('White Sugar Sachet 7g',     5.35),
            ('Brown Sugar Sachet 5g',     5.10),
            ('Brown Sugar Sachet 7g',     5.80),
            ('White Sugar Stick 5g',      4.65),
            ('Brown Sugar Stick 5g',      5.35),
            ('Creamer Sachet 5g',        22.50),
            ('Green Tea Envelopes',      18.00),
            ('Black Tea Envelopes',      15.00),
            ('Catering Tea Pack',       770.00),
            ('Instant Coffee 1.2g',      24.50),
            ('Coffee Mate 5g',           34.00),
            ('Salt 1g',                   3.20),
            ('Pepper 0.5g',               7.25),
        ],
    },
]


class Command(BaseCommand):
    help = 'Seed product categories and products for Everbolt Food ERP'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing products and categories before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing products and categories...')
            Product.objects.all().delete()
            Category.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared all products and categories.'))

        total_created = 0
        total_skipped = 0

        for group in PRODUCTS_DATA:
            cat_name = group['category']
            category, cat_created = Category.objects.get_or_create(name=cat_name)
            if cat_created:
                self.stdout.write(self.style.SUCCESS(f'  Created category: {cat_name}'))
            else:
                self.stdout.write(f'  Category already exists: {cat_name}')

            for product_name, price in group['items']:
                if Product.objects.filter(name=product_name, category=category).exists():
                    self.stdout.write(f'    Skipping (already exists): {product_name}')
                    total_skipped += 1
                    continue

                product = Product(
                    name=product_name,
                    category=category,
                    selling_price=price,
                    selling_unit='PCS',
                    product_type='MANUFACTURED',
                    current_stock=0,
                    status=True,
                )
                product.save()  # triggers auto product_id and SKU generation
                self.stdout.write(
                    self.style.SUCCESS(f'    [{product.product_id}] {product.sku} → Rs.{price}')
                )
                total_created += 1

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f'Done! Created {total_created} products, skipped {total_skipped} duplicates.'
        ))
