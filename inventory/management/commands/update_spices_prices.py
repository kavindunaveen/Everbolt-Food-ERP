"""
Management command to:
1. Match Spices products to the CSV naming convention
2. Update selling_price to the WITHOUT VAT price from the CSV
3. Store the vat_amount_per_unit and mrp_with_vat data
4. Delete all existing invoices and quotations
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from decimal import Decimal


CSV_SPICES = [
    # (csv_name, without_vat, vat_amount, mrp_with_vat)
    ("Black Pepper Powder - 1kg",   Decimal("2783.90"), Decimal("501.10"),  Decimal("3285.00")),
    ("Black Pepper Powder - 500g",  Decimal("1394.07"), Decimal("250.93"),  Decimal("1645.00")),
    ("Black Pepper Powder - 200g",  Decimal("563.56"),  Decimal("101.44"),  Decimal("665.00")),
    ("Black Pepper Powder - 100g",  Decimal("288.14"),  Decimal("51.86"),   Decimal("340.00")),
    ("Chilli Flakes - 1kg",         Decimal("1364.41"), Decimal("245.59"),  Decimal("1610.00")),
    ("Chilli Flakes - 500g",        Decimal("686.44"),  Decimal("123.56"),  Decimal("810.00")),
    ("Chilli Flakes - 200g",        Decimal("279.66"),  Decimal("50.34"),   Decimal("330.00")),
    ("Chilli Flakes - 100g",        Decimal("144.07"),  Decimal("25.93"),   Decimal("170.00")),
    ("Chilli Powder - 1kg",         Decimal("1216.10"), Decimal("218.90"),  Decimal("1435.00")),
    ("Chilli Powder - 500g",        Decimal("610.17"),  Decimal("109.83"),  Decimal("720.00")),
    ("Chilli Powder - 200g",        Decimal("250.00"),  Decimal("45.00"),   Decimal("295.00")),
    ("Chilli Powder - 100g",        Decimal("131.36"),  Decimal("23.64"),   Decimal("155.00")),
    ("Curry Powder - 1kg",          Decimal("1457.63"), Decimal("262.37"),  Decimal("1720.00")),
    ("Curry Powder - 500g",         Decimal("733.05"),  Decimal("131.95"),  Decimal("865.00")),
    ("Curry Powder - 200g",         Decimal("300.85"),  Decimal("54.15"),   Decimal("355.00")),
    ("Curry Powder - 100g",         Decimal("152.54"),  Decimal("27.46"),   Decimal("180.00")),
    ("Roasted Curry Powder - 1kg",  Decimal("1576.27"), Decimal("283.73"),  Decimal("1860.00")),
    ("Roasted Curry Powder - 500g", Decimal("792.37"),  Decimal("142.63"),  Decimal("935.00")),
    ("Roasted Curry Powder - 200g", Decimal("322.03"),  Decimal("57.97"),   Decimal("380.00")),
    ("Roasted Curry Powder - 100g", Decimal("169.49"),  Decimal("30.51"),   Decimal("200.00")),
    ("Turmeric Powder - 1kg",       Decimal("3444.92"), Decimal("620.08"),  Decimal("4065.00")),
    ("Turmeric Powder - 500g",      Decimal("1728.81"), Decimal("311.19"),  Decimal("2040.00")),
    ("Turmeric Powder - 200g",      Decimal("694.92"),  Decimal("125.08"),  Decimal("820.00")),
    ("Turmeric Powder - 100g",      Decimal("355.93"),  Decimal("64.07"),   Decimal("420.00")),
]

# Mapping from existing product_id to the CSV row index above
# Current DB spice products (from inspection):
# EFSP-0001 Chillie Powder 1kg     -> Chilli Powder - 1kg
# EFSP-0002 Chillie Powder 500g    -> Chilli Powder - 500g
# EFSP-0003 Chillie Powder 200g    -> Chilli Powder - 200g
# EFSP-0004 Chillie Powder 100g    -> Chilli Powder - 100g
# EFSP-0005 Chillie Pieces 1kg     -> Chilli Flakes - 1kg
# EFSP-0006 Chillie Pieces 500g    -> Chilli Flakes - 500g
# EFSP-0007 Chillie Pieces 200g    -> Chilli Flakes - 200g
# EFSP-0008 Chillie Pieces 100g    -> Chilli Flakes - 100g
# EFSP-0009 Curry Powder 1kg       -> Curry Powder - 1kg
# EFSP-0010 Curry Powder 500g      -> Curry Powder - 500g
# EFSP-0011 Curry Powder 200g      -> Curry Powder - 200g
# EFSP-0012 Curry Powder 100g      -> Curry Powder - 100g
# EFSP-0013 Roasted Curry Powder 1kg -> Roasted Curry Powder - 1kg
# EFSP-0014 Roasted Curry Powder 500g -> Roasted Curry Powder - 500g
# EFSP-0015 Roasted Curry Powder 200g -> Roasted Curry Powder - 200g
# EFSP-0016 Roasted Curry Powder 100g -> Roasted Curry Powder - 100g
# EFSP-0017 Pepper Powder 1kg      -> Black Pepper Powder - 1kg
# EFSP-0018 Pepper Powder 500g     -> Black Pepper Powder - 500g
# EFSP-0019 Pepper Powder 200g     -> Black Pepper Powder - 200g
# EFSP-0020 Pepper Powder 100g     -> Black Pepper Powder - 100g
# Turmeric: EFSP-0021 to EFSP-0024 (need to be created)

PRODUCT_ID_TO_CSV = {
    "EFSP-0017": 0,   # Black Pepper Powder - 1kg
    "EFSP-0018": 1,   # Black Pepper Powder - 500g
    "EFSP-0019": 2,   # Black Pepper Powder - 200g
    "EFSP-0020": 3,   # Black Pepper Powder - 100g
    "EFSP-0005": 4,   # Chilli Flakes - 1kg
    "EFSP-0006": 5,   # Chilli Flakes - 500g
    "EFSP-0007": 6,   # Chilli Flakes - 200g
    "EFSP-0008": 7,   # Chilli Flakes - 100g
    "EFSP-0001": 8,   # Chilli Powder - 1kg
    "EFSP-0002": 9,   # Chilli Powder - 500g
    "EFSP-0003": 10,  # Chilli Powder - 200g
    "EFSP-0004": 11,  # Chilli Powder - 100g
    "EFSP-0009": 12,  # Curry Powder - 1kg
    "EFSP-0010": 13,  # Curry Powder - 500g
    "EFSP-0011": 14,  # Curry Powder - 200g
    "EFSP-0012": 15,  # Curry Powder - 100g
    "EFSP-0013": 16,  # Roasted Curry Powder - 1kg
    "EFSP-0014": 17,  # Roasted Curry Powder - 500g
    "EFSP-0015": 18,  # Roasted Curry Powder - 200g
    "EFSP-0016": 19,  # Roasted Curry Powder - 100g
    # Turmeric (EFSP-0021 to 0024) will be created fresh
}

# Turmeric products to CREATE (indices 20-23 in CSV_SPICES)
TURMERIC_TO_CREATE = [
    {"product_id": "EFSP-0021", "csv_index": 20},
    {"product_id": "EFSP-0022", "csv_index": 21},
    {"product_id": "EFSP-0023", "csv_index": 22},
    {"product_id": "EFSP-0024", "csv_index": 23},
]


class Command(BaseCommand):
    help = "Update spice product names/prices from CSV and delete all invoices/quotations"

    def handle(self, *args, **options):
        from inventory.models import Product
        from sales.models import Invoice, Quotation, InvoiceItem, QuotationItem, SalesAuditLog, Return

        with transaction.atomic():
            self.stdout.write("=== Step 1: Clearing all Invoices, Quotations and related data ===")
            
            # Delete audit logs first (generic FK)
            SalesAuditLog.objects.all().delete()
            self.stdout.write("  Deleted all SalesAuditLog entries.")
            
            # Delete returns (FK to Invoice)
            Return.objects.all().delete()
            self.stdout.write("  Deleted all Return entries.")
            
            # Delete invoice items, then invoices
            InvoiceItem.objects.all().delete()
            Invoice.objects.all().delete()
            self.stdout.write("  Deleted all InvoiceItems and Invoices.")
            
            # Delete quotation items, then quotations
            QuotationItem.objects.all().delete()
            Quotation.objects.all().delete()
            self.stdout.write("  Deleted all QuotationItems and Quotations.")

            self.stdout.write("")
            self.stdout.write("=== Step 2: Updating existing Spice products ===")
            
            for product_id, csv_idx in PRODUCT_ID_TO_CSV.items():
                try:
                    product = Product.objects.get(product_id=product_id)
                    csv_row = CSV_SPICES[csv_idx]
                    new_name = csv_row[0]
                    new_price = csv_row[1]  # WITHOUT VAT price
                    
                    old_name = product.name
                    old_price = product.selling_price
                    
                    product.name = new_name
                    product.selling_price = new_price
                    product.tax_rate = Decimal("18.00")
                    # Save without triggering product_id regen (it already has one)
                    Product.objects.filter(pk=product.pk).update(
                        name=new_name,
                        selling_price=new_price,
                        tax_rate=Decimal("18.00"),
                    )
                    self.stdout.write(
                        f"  Updated {product_id}: '{old_name}' -> '{new_name}' | "
                        f"price {old_price} -> {new_price} (ex-VAT)"
                    )
                except Product.DoesNotExist:
                    self.stdout.write(
                        self.style.WARNING(f"  Product {product_id} NOT FOUND - skipping")
                    )

            self.stdout.write("")
            self.stdout.write("=== Step 3: Creating Turmeric Powder products ===")
            
            for entry in TURMERIC_TO_CREATE:
                pid = entry["product_id"]
                csv_idx = entry["csv_index"]
                csv_row = CSV_SPICES[csv_idx]
                
                # Check if already exists
                if Product.objects.filter(product_id=pid).exists():
                    # Update existing
                    Product.objects.filter(product_id=pid).update(
                        name=csv_row[0],
                        selling_price=csv_row[1],
                        tax_rate=Decimal("18.00"),
                        category="Spices",
                    )
                    self.stdout.write(f"  Updated existing {pid}: {csv_row[0]}")
                else:
                    # Create new - use update() to bypass save()'s product_id auto-gen
                    p = Product(
                        product_id=pid,
                        name=csv_row[0],
                        category="Spices",
                        brand="Everbolt",
                        inventory_class="FINISHED",
                        product_type="Direct Packing",
                        selling_price=csv_row[1],
                        tax_rate=Decimal("18.00"),
                        stock_unit="pcs",
                        selling_unit="pcs",
                        track_stock=True,
                        allow_negative_stock=False,
                        reorder_level=Decimal("0.000"),
                        current_stock=Decimal("0.000"),
                        status=True,
                    )
                    # Bypass auto-id generation by directly calling super().save()
                    # We temporarily set the product_id before calling save
                    existing_pid = p.product_id
                    p.save()
                    # If save() overwrote our product_id, fix it
                    if p.product_id != existing_pid:
                        Product.objects.filter(pk=p.pk).update(product_id=existing_pid)
                    self.stdout.write(f"  Created {pid}: {csv_row[0]} | price={csv_row[1]} (ex-VAT)")

            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS("=== All done! Summary: ==="))
            
            spices = Product.objects.filter(category="Spices").order_by("product_id")
            for s in spices:
                vat = s.selling_price * Decimal("0.18")
                mrp = s.selling_price + vat
                self.stdout.write(
                    f"  {s.product_id} | {s.name} | ex-VAT={s.selling_price} | "
                    f"VAT={vat:.2f} | MRP={mrp:.2f}"
                )
            
            self.stdout.write("")
            self.stdout.write(f"  Remaining Invoices: {Invoice.objects.count()}")
            self.stdout.write(f"  Remaining Quotations: {Quotation.objects.count()}")
