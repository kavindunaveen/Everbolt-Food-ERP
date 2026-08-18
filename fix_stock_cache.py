"""
One-time fix script:
1. Recalculates current_stock cache from ledger for ALL products
2. Reverses the wrong SYS-IMPORT ledger entries from today's bad import
   (which were based on the drifted cache instead of real ledger balance)
3. Creates correct replacement ledger entries

Run: python manage.py shell < fix_stock_cache.py
"""
from inventory.models import StockLedger, Product
from django.db.models import Sum
from decimal import Decimal
from django.utils import timezone
import datetime

# -------------------------
# Step 1: Find today's bad import entries and reverse them
# -------------------------
cutoff = timezone.now() - datetime.timedelta(hours=12)
today_imports = StockLedger.objects.filter(reference_type='SYS-IMPORT', date__gte=cutoff)
print(f"Today's SYS-IMPORT entries to reverse: {today_imports.count()}")

# Get all affected products BEFORE deleting the bad entries
affected_products = list(today_imports.values_list('product_id', flat=True).distinct())

# Delete today's bad import ledger entries (they were based on wrong cache values)
today_imports.delete()
print(f"Deleted bad import entries.")
print()

# -------------------------
# Step 2: For each affected product, recalculate true balance from REMAINING ledger
# then compare with what Excel had set the cache to, and create a correct adjustment
# -------------------------
# We don't have the Excel values anymore, but we know:
# - The cache was SET to the Excel value by today's import (product.current_stock = qty)
# - So product.current_stock currently = what Excel wanted
# We just need to make the ledger match that target.

fixed_count = 0
skipped_count = 0

for prod_id in affected_products:
    p = Product.objects.filter(id=prod_id).first()
    if not p:
        continue

    # True ledger balance after removing bad today entries
    ledger_result = StockLedger.objects.filter(product=p).aggregate(
        bal=Sum('qty_in') - Sum('qty_out')
    )
    ledger_balance = ledger_result['bal'] or Decimal('0.000')

    # Current cache = what Excel wanted (set by today's import)
    target_qty = p.current_stock

    diff = target_qty - ledger_balance

    if diff == 0:
        # Cache matches ledger already — just ensure cache is correct
        skipped_count += 1
        continue

    # Create a correct ledger entry bridging the gap
    tx_type = StockLedger.TransactionTypes.ADJ_POS if diff > 0 else StockLedger.TransactionTypes.ADJ_NEG
    qty_in = diff if diff > 0 else Decimal('0.000')
    qty_out = -diff if diff < 0 else Decimal('0.000')

    StockLedger.objects.create(
        product=p,
        tx_type=tx_type,
        qty_in=qty_in,
        qty_out=qty_out,
        reference_type='SYS-IMPORT',
        reference_number='IMPORT-FIX',
        remarks='Corrected import: based on real ledger balance',
        user=None
    )
    fixed_count += 1
    print(f"  Fixed [{p.product_id}] {p.name}: ledger_was={ledger_balance}, target={target_qty}, adj={diff}")

print()
print(f"Fixed: {fixed_count} products, Skipped (already correct): {skipped_count}")

# -------------------------
# Step 3: Recalculate cache for ALL products from ledger
# -------------------------
print()
print("Recalculating current_stock cache for ALL products from ledger...")
all_products = Product.objects.filter(track_stock=True)
cache_fixed = 0
cache_ok = 0

for p in all_products:
    ledger_result = StockLedger.objects.filter(product=p).aggregate(
        bal=Sum('qty_in') - Sum('qty_out')
    )
    true_balance = ledger_result['bal'] or Decimal('0.000')
    if p.current_stock != true_balance:
        print(f"  Cache fix [{p.product_id}] {p.name}: was={p.current_stock}, corrected to={true_balance}")
        Product.objects.filter(pk=p.pk).update(current_stock=true_balance)
        cache_fixed += 1
    else:
        cache_ok += 1

print()
print(f"Cache corrections: {cache_fixed} products updated, {cache_ok} already correct.")
print("Done.")
