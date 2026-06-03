import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()

from django.db.models import Sum, F
from django.utils import timezone
from sales.models import Invoice, InvoiceItem, CreditNote
from dashboard.views import CONFEC_BUCKETS, classify_product

target_year = 2026
target_month = 6 # assuming june for test, let's use current month
now = timezone.now()
target_year = now.year
target_month = now.month

print(f"--- VERIFYING DATA FOR {target_year}-{target_month:02d} ---")

inv_qs = Invoice.objects.filter(
    creation_date__year=target_year, 
    creation_date__month=target_month,
    status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
)

print(f"Total Issued/Paid Invoices: {inv_qs.count()}")

# 1. Overall Sales Method 1: dashboard/views.py DashboardDataAPI
revenue_ex_vat = inv_qs.annotate(inv_ex_vat=F('total_amount') - F('tax_amount')).aggregate(Sum('inv_ex_vat'))['inv_ex_vat__sum'] or Decimal('0.00')
credit_notes = CreditNote.objects.filter(original_invoice__in=inv_qs)
credit_subtotal = sum((cn.quantity * cn.unit_price) for cn in credit_notes)
overall_sales_dash = float(revenue_ex_vat - Decimal(str(credit_subtotal)))
print(f"Dashboard Overall Sales: {overall_sales_dash}")

# 2. Overall Sales Method 2: forecasting/views.py ForecastingView
# Wait, ForecastingView doesn't subtract credit notes! Let's check what it calculates.
total_sales_forecast = inv_qs.annotate(ex_vat=F('total_amount') - F('tax_amount')).aggregate(total=Sum('ex_vat'))['total'] or 0
print(f"Forecasting Total Sales (before CN): {float(total_sales_forecast)}")

# 3. Let's calculate the sum of all items manually using the two-pass proportional logic.
invoices = inv_qs.values('id', 'custom_discount_type', 'custom_discount_value')
inv_map = { i['id']: i for i in invoices }
items = InvoiceItem.objects.filter(invoice__in=inv_qs).values(
    'invoice_id', 'product__category', 'product__name', 'quantity', 'unit_price', 'discount_type', 'discount'
)

inv_gross_sums = {}
processed_items = []
for item in items:
    q = Decimal(str(item['quantity']))
    p = Decimal(str(item['unit_price']))
    d_val = Decimal(str(item['discount'] or 0))
    if item['discount_type'] == 'PERCENT':
        line_disc = (q * p) * (d_val / Decimal('100.0'))
    else:
        line_disc = d_val
        
    item_gross = (q * p) - line_disc
    inv_id = item['invoice_id']
    inv_gross_sums[inv_id] = inv_gross_sums.get(inv_id, Decimal('0.00')) + item_gross
    
    processed_items.append({
        'item': item,
        'gross': item_gross,
        'inv_id': inv_id
    })

cat_sums = {'confectionery': Decimal('0.0'), 'sugar': Decimal('0.0'), 'creamer': Decimal('0.0'), 'tea': Decimal('0.0'), 'other': Decimal('0.0')}
total_item_sales_after_global = Decimal('0.0')

for p_item in processed_items:
    inv = inv_map[p_item['inv_id']]
    inv_gross = inv_gross_sums[p_item['inv_id']]
    item_gross = p_item['gross']
    
    c_type = inv['custom_discount_type']
    c_val = Decimal(str(inv['custom_discount_value'] or 0))
    
    if c_type == 'PERCENT':
        final_val = item_gross * (Decimal('1.0') - (c_val / Decimal('100.0')))
    else:
        if inv_gross > 0:
            ratio = item_gross / inv_gross
            final_val = item_gross - (ratio * c_val)
        else:
            final_val = item_gross
            
    total_item_sales_after_global += final_val
            
    cat = (p_item['item']['product__category'] or '').lower()
    name = (p_item['item']['product__name'] or '').lower()
    
    matched = False
    if 'confectionery' in cat:
        cat_sums['confectionery'] += final_val
        matched = True
    elif 'sugar' in cat or 'sugar' in name:
        cat_sums['sugar'] += final_val
        matched = True
    elif 'creamer' in cat or 'creamer' in name:
        cat_sums['creamer'] += final_val
        matched = True
    elif 'tea' in cat or 'tea' in name:
        cat_sums['tea'] += final_val
        matched = True
        
    if not matched:
        cat_sums['other'] += final_val

print(f"Sum of all items after global discount: {float(total_item_sales_after_global)}")
print(f"Difference between Dashboard Overall Sales (before CN) and sum of items: {float(revenue_ex_vat - total_item_sales_after_global)}")

# Now deduct CNs for categories
conf_credits = sum((cn.quantity * cn.unit_price) for cn in credit_notes.filter(product__category__icontains='Confectionery'))
confectionery_sales = float(cat_sums['confectionery'] - Decimal(str(conf_credits)))

from django.db.models import Q
sugar_credits = sum((cn.quantity * cn.unit_price) for cn in credit_notes.filter(Q(product__category__icontains='Sugar') | Q(product__name__icontains='Sugar')))
sugar_sales = float(cat_sums['sugar'] - Decimal(str(sugar_credits)))

creamer_credits = sum((cn.quantity * cn.unit_price) for cn in credit_notes.filter(Q(product__category__icontains='Creamer') | Q(product__name__icontains='Creamer')))
creamer_sales = float(cat_sums['creamer'] - Decimal(str(creamer_credits)))

tea_credits = sum((cn.quantity * cn.unit_price) for cn in credit_notes.filter(Q(product__category__icontains='Tea') | Q(product__name__icontains='Tea')))
tea_sales = float(cat_sums['tea'] - Decimal(str(tea_credits)))

other_credits = sum((cn.quantity * cn.unit_price) for cn in credit_notes.exclude(product__category__icontains='Confectionery').exclude(Q(product__category__icontains='Sugar') | Q(product__name__icontains='Sugar')).exclude(Q(product__category__icontains='Creamer') | Q(product__name__icontains='Creamer')).exclude(Q(product__category__icontains='Tea') | Q(product__name__icontains='Tea')))
other_sales = float(cat_sums['other'] - Decimal(str(other_credits)))

print(f"Category Sales (after CN):")
print(f"  Confectionery: {confectionery_sales}")
print(f"  Sugar: {sugar_sales}")
print(f"  Creamer: {creamer_sales}")
print(f"  Tea: {tea_sales}")
print(f"  Other: {other_sales}")

sum_categories = confectionery_sales + sugar_sales + creamer_sales + tea_sales + other_sales
print(f"Sum of Categories: {sum_categories}")
print(f"Difference (Dashboard Overall vs Sum of Categories): {overall_sales_dash - sum_categories}")

