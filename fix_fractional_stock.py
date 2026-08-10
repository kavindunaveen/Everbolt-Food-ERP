import os
import django
from decimal import Decimal

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from inventory.models import Product, StockAdjustment
from django.contrib.auth import get_user_model

User = get_user_model()
system_user = User.objects.filter(is_superuser=True).first()

int_units = ['pcs', 'packets', 'pack', 'bottles', 'schachets/sticks', 'box']

products = Product.objects.all()
fixed_count = 0

for p in products:
    if p.stock_unit and p.stock_unit.lower().strip() in int_units:
        if p.current_stock % 1 != 0:
            nearest = round(p.current_stock)
            adjustment_amount = nearest - p.current_stock
            
            if adjustment_amount != 0:
                adj_type = StockAdjustment.AdjustmentTypes.POSITIVE if adjustment_amount > 0 else StockAdjustment.AdjustmentTypes.NEGATIVE
                
                adj = StockAdjustment(
                    date=django.utils.timezone.now().date(),
                    product=p,
                    adjustment_type=adj_type,
                    quantity=abs(adjustment_amount),
                    reason="Rounding fractional stock for whole-unit product",
                    remarks="Automated system fix to reverse erroneous decimal transactions",
                    status=StockAdjustment.StatusChoices.CONFIRMED,
                    created_by=system_user
                )
                
                # Assign a sequence number manually since save() is bypassed
                last_adj = StockAdjustment.objects.order_by('-id').first()
                seq = (int(last_adj.adjustment_number.split('-')[-1]) + 1) if (last_adj and last_adj.adjustment_number.startswith('ADJ-')) else 1
                adj.adjustment_number = f"ADJ-{seq:04d}"
                
                StockAdjustment.objects.bulk_create([adj])
                adj = StockAdjustment.objects.get(adjustment_number=adj.adjustment_number)
                
                from inventory.models import StockLedger
                tx_type = StockLedger.TransactionTypes.ADJ_POS if adjustment_amount > 0 else StockLedger.TransactionTypes.ADJ_NEG
                qty_in = abs(adjustment_amount) if adjustment_amount > 0 else 0
                qty_out = abs(adjustment_amount) if adjustment_amount < 0 else 0
                
                sl = StockLedger(
                    product=p,
                    tx_type=tx_type,
                    qty_in=qty_in,
                    qty_out=qty_out,
                    reference_type='ADJ',
                    reference_id=adj.id,
                    reference_number=adj.adjustment_number,
                    remarks=adj.remarks,
                    user=system_user
                )
                StockLedger.objects.bulk_create([sl])
                
                Product.objects.filter(pk=p.pk).update(current_stock=p.current_stock + adjustment_amount)
                
                print(f"Fixed {p.name}: Adjusted by {adjustment_amount}. New stock: {p.current_stock + adjustment_amount}")
                fixed_count += 1

print(f"Total products fixed: {fixed_count}")
