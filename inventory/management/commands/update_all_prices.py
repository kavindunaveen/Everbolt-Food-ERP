"""
Management command to update ALL product prices from the Excel workbook.
Updates: Kithul, Artisan Tea, Herbs (Herbal Tea), Flavoured Tea, 
         Dehydrated Fruits & Vegetables, Confectionery
Prices are stored as Ex-VAT (without VAT). VAT is 18% added at invoice time.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal, ROUND_HALF_UP


def d(val):
    """Round to 2 decimal places."""
    return Decimal(str(val)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


# ─────────────────────────────────────────────────────────────────────────────
# Data extracted from Excel (Ex-VAT prices = MRP / 1.18)
# MRP = the price in the Excel "MRP With VAT Price" column
# Ex-VAT = MRP / 1.18  (which is what Excel computes as "Without VAT Price")
# ─────────────────────────────────────────────────────────────────────────────

# Kithul Sheet — product_id → (excel_name, ex_vat_price, mrp)
KITHUL = [
    # DB name                               Excel name                        ex_vat           mrp
    ('EFKT-0004', 'Kithul Flour 250g',      'Kithul Flour - 250g',            d(610.17),  d(720.00)),
    ('EFKT-0006', 'Kithul Jaggery Pieces 200g','Kithul Jaggery Pieces - 200g',d(898.31),  d(1060.01)),
    ('EFKT-0003', 'Kithul Sugar Powder 200g','Kithul Sugar Powder - 200g',    d(949.15),  d(1120.00)),
    ('EFKT-0001', 'Kithul Treacle - S - 375ml','Kithul Treacle - S - 375ml', d(1813.56), d(2140.00)),
    ('EFKT-0002', 'Kithul Treacle - Round - 375ml','Kithul Treacle - Round - 375ml',d(1440.68),d(1700.00)),
    ('EFKT-0005', 'Kithul Half - 500ml',    'Kithul Half - 500ml',            d(2033.90), d(2400.00)),
]

# Artisan Tea Sheet — maps to Tea category (EFTE-0027 to 0034)
ARTISAN = [
    ('EFTE-0027', 'Everleaf Artisan Green Tea 50g',         'Everleaf Artisan Green Tea - 50g',         d(1516.95), d(1790.00)),
    ('EFTE-0028', 'Everleaf Artisan Green Tea 100g',        'Everleaf Artisan Green Tea - 100g',        d(2161.02), d(2550.00)),
    ('EFTE-0029', 'Everleaf Artisan Black Tea 50g',         'Everleaf Artisan Black Tea - 50g',         d(1516.95), d(1790.00)),
    ('EFTE-0030', 'Everleaf Artisan Black Tea 100g',        'Everleaf Artisan Black Tea - 100g',        d(2161.02), d(2550.00)),
    ('EFTE-0031', 'Everleaf Artisan White Tea 50g',         'Everleaf Artisan White Tea - 50g',         d(1516.95), d(1790.00)),
    ('EFTE-0032', 'Everleaf Artisan White Tea 100g',        'Everleaf Artisan White Tea - 100g',        d(2161.02), d(2550.00)),
    ('EFTE-0033', 'Everleaf Arisan Wangedi Pakoe 50g',      'Everleaf Arisan Wangedi Pakoe - 50g',      d(1144.07), d(1350.00)),
    ('EFTE-0034', 'Everleaf Arisan Wangedi Pakoe 100g',     'Everleaf Arisan Wangedi Pakoe - 100g',     d(1483.05), d(1750.00)),
]

# Herbs Sheet — Herbal Tea products (EFTE-0001 to 0016)
HERBS = [
    ('EFTE-0001', 'Ushma',          'Ushma - 30g',          d(1008.47), d(1190.00)),
    ('EFTE-0002', 'Slim Herb',      'Slim Herb  - 30g',     d(1008.47), d(1190.00)),
    ('EFTE-0003', 'Island Spicy Fusion','Island Spicy Fusion - 30g',d(932.20),d(1100.00)),
    ('EFTE-0004', 'Special Hibiscus','Special Hibiscus - 30g',d(1059.32),d(1250.00)),
    ('EFTE-0005', 'Herbal Soothe',  'Herbal Soothe - 30g',  d(847.46),  d(1000.00)),
    ('EFTE-0006', 'Harmony Brew',   'Harmony Brew - 30g',   d(1076.27), d(1270.00)),
    ('EFTE-0007', 'Fat Burn',       'Fat Burn - 30g',       d(974.58),  d(1150.00)),
    ('EFTE-0008', 'Detox',          'Detox - 30g',          d(940.68),  d(1110.00)),
    ('EFTE-0009', 'Citrus',         'Citrus - 30g',         d(1000.00), d(1180.00)),
    ('EFTE-0010', 'Calm Mind',      'Calm Mind - 30g',      d(1050.85), d(1240.00)),
    ('EFTE-0011', 'Balance Blend',  'Balance Blend - 30g',  d(974.58),  d(1150.00)),
    ('EFTE-0012', 'Moringa Morning','Moringa Morning - 30g', d(872.88),  d(1030.00)),
    ('EFTE-0013', 'Immuno Up',      'Immuno Up - 30g',      d(974.58),  d(1150.00)),
    ('EFTE-0014', 'Glyco guard',    'Glyco guard - 30g',    d(847.46),  d(1000.00)),
    ('EFTE-0015', 'Green Guard',    'Green Guard - 30g',    d(923.73),  d(1090.00)),
    ('EFTE-0016', 'Vita Cure',      'Vita Cure - 30g',      d(898.31),  d(1060.00)),
]

# Flavoured Tea Sheet (EFTE-0017 to 0026)
FLAVOURED = [
    ('EFTE-0017', 'Jasmine Flavored Tea',       'Jasmine green tea with natural buds - 50g', d(805.08),  d(950.00)),
    ('EFTE-0018', 'Mango Flavored Tea',         'Mango black tea - 30g',                     d(533.90),  d(630.00)),
    ('EFTE-0019', 'Ginger Flavored Tea',        'Ginger black tea - 30g',                    d(588.98),  d(695.00)),
    ('EFTE-0020', 'Caramel Flavored Tea',       'Caramel black tea - 30g',                   d(546.61),  d(645.00)),
    ('EFTE-0021', 'Lemon Green Tea Flavored Tea','Lemon Green Tea - 30g',                    d(572.03),  d(675.00)),
    ('EFTE-0022', 'Pineapple Flavored Tea',     'Pineapple black tea - 30g',                 d(559.32),  d(660.00)),
    ('EFTE-0023', 'Strawberry Flavored Tea',    'Strawberry black tea - 30g',                d(550.85),  d(650.00)),
    ('EFTE-0024', 'Passion Fruit Flavored Tea', 'Passion Fruit black tea - 30g',             d(762.71),  d(900.00)),
    ('EFTE-0025', 'Green Tea Box',              'Green tea - 30g',                           d(550.85),  d(650.00)),
    ('EFTE-0026', 'Black Tea Box',              'Black tea - 30g',                           d(495.76),  d(585.00)),
]

# Dehydrated Products Sheet
DEHYDRATED = [
    # Dried Vegetables
    ('EFDV-0001', 'Dehydrated Bitter Gourd - 50g',   d(656.78),  d(775.00)),
    ('EFDV-0002', 'Dehydrated Breadfruit - 50g',     d(444.92),  d(525.00)),
    ('EFDV-0003', 'Dehydrated Curry Leaves - 50g',   d(330.51),  d(390.00)),
    ('EFDV-0004', 'Dehydrated Jackfruit - 50g',      d(372.88),  d(440.00)),
    ('EFDV-0005', 'Dehydrated Leaks - 50g',          d(521.19),  d(615.00)),
    # Dried Fruits
    ('EFDF-0001', 'Dehydrated Banana - 50g',         d(288.14),  d(340.00)),
    ('EFDF-0002', 'Dehydrated Mango - 50g',          d(411.02),  d(485.00)),
    ('EFDF-0003', 'Dehydrated Papaya - 50g',         d(389.83),  d(460.00)),
    ('EFDF-0004', 'Dehydrated Pineapple rings - 50g',d(576.27),  d(680.00)),
    # Vegetable Powders
    ('EFDV-0006', 'Beetroot Powder - 50g',           d(457.63),  d(540.00)),
    ('EFDV-0007', 'Carrot Powder - 50g',             d(453.39),  d(535.00)),
    ('EFDV-0008', 'Curry Leaves Powder - 50g',       d(300.85),  d(355.00)),
    ('EFDV-0009', 'Moringa Powder - 50g',            d(351.69),  d(415.00)),
    ('EFDV-0010', 'Pumpkin Powder - 50g',            d(411.02),  d(485.00)),
    ('EFDV-0011', 'Tomato Powder - 50g',             d(466.10),  d(550.00)),
]

# Confectionery Sheet — uses MRP (col F = "100 pcs" tier) as the standard MRP
# Ex-VAT = MRP / 1.18
CONFECTIONERY = [
    # product_id,  db_name,                         ex_vat,      mrp
    ('ESW001',  'Sugar sachet - White - 5g',         d(4.24),     d(5.00)),
    ('ESB001',  'Sugar sachet - Brown - 5g',         d(4.66),     d(5.50)),
    ('ESW002',  'Sugar sachet - White - 7g',         d(4.87),     d(5.75)),
    ('ESB002',  'Sugar sachet - Brown - 7g',         d(5.21),     d(6.15)),
    ('ESWS001', 'Sugar stick - White - 5g',          d(4.45),     d(5.25)),
    ('ESBS001', 'Sugar stick - Brown - 5g',          d(5.08),     d(6.00)),
    ('ESWS002', 'Sugar stick - White - 7g',          d(5.04),     d(5.95)),
    ('ESBS002', 'Sugar stick - Brown - 7g',          d(5.64),     d(6.65)),
    ('ECR001',  'Creamer Sachet - 5g',               d(21.19),    d(25.00)),
    ('ETE001',  'EverLeaf Tea Envelop - 2g',         d(14.41),    d(17.00)),
    ('ENCF001', 'Nescafe Instant coffee - 1.2g',     d(21.19),    d(25.00)),
    ('ECFM001', 'Coffee Mate - 5g',                  d(28.81),    d(34.00)),
    ('ETB001',  'Tea Bag (catering Tea)',             d(677.97),   d(800.00)),
    ('ETE002',  'EverLeaf Green Tea Envelope',       d(15.76),    d(18.60)),
]


class Command(BaseCommand):
    help = "Update ALL product prices (ex-VAT) from the Excel workbook data"

    def handle(self, *args, **options):
        from inventory.models import Product

        total_updated = 0
        total_skipped = 0

        with transaction.atomic():

            def update_group(group_name, entries, use_product_id=True):
                nonlocal total_updated, total_skipped
                self.stdout.write(f"\n=== {group_name} ===")
                for entry in entries:
                    if use_product_id:
                        pid, db_name, *rest = entry
                        ex_vat = rest[-2] if len(rest) == 3 else rest[0]
                        # entries format: (pid, db_name, excel_name, ex_vat, mrp) OR (pid, db_name, ex_vat, mrp)
                        if len(rest) == 3:
                            _, ex_vat, mrp = rest
                        else:
                            ex_vat, mrp = rest
                        try:
                            p = Product.objects.get(product_id=pid)
                            old_price = p.selling_price
                            Product.objects.filter(pk=p.pk).update(
                                selling_price=ex_vat,
                                tax_rate=Decimal('18.00'),
                            )
                            self.stdout.write(
                                f"  ✅ {pid} | {p.name} | {old_price} → {ex_vat} (MRP: {mrp})"
                            )
                            total_updated += 1
                        except Product.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f"  ⚠️  {pid} NOT FOUND in DB — skipping")
                            )
                            total_skipped += 1
                    else:
                        # Confectionery: (product_code, db_name, ex_vat, mrp)
                        code, db_name, ex_vat, mrp = entry
                        try:
                            p = Product.objects.get(product_id=code)
                            old_price = p.selling_price
                            Product.objects.filter(pk=p.pk).update(
                                selling_price=ex_vat,
                                tax_rate=Decimal('18.00'),
                            )
                            self.stdout.write(
                                f"  ✅ {code} | {p.name} | {old_price} → {ex_vat} (MRP: {mrp})"
                            )
                            total_updated += 1
                        except Product.DoesNotExist:
                            self.stdout.write(
                                self.style.WARNING(f"  ⚠️  {code} NOT FOUND — skipping")
                            )
                            total_skipped += 1

            update_group("Kithul Products", KITHUL)
            update_group("Artisan Tea (Tea category)", ARTISAN)
            update_group("Herbal Tea (Herbs)", HERBS)
            update_group("Flavoured Tea", FLAVOURED)
            update_group("Dehydrated Fruits & Vegetables", DEHYDRATED)
            update_group("Confectionery", CONFECTIONERY, use_product_id=False)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"=== DONE: {total_updated} updated, {total_skipped} skipped ==="
        ))
        self.stdout.write("")
        self.stdout.write("=== FULL PRODUCT PRICE SUMMARY ===")
        for p in Product.objects.all().order_by('category', 'product_id'):
            mrp = (p.selling_price * Decimal('1.18')).quantize(Decimal('0.01'))
            self.stdout.write(
                f"  {p.product_id:<12} | {p.category:<20} | {p.name:<45} | ex-VAT={p.selling_price} | MRP≈{mrp}"
            )
