from sales.models import Invoice, InvoiceItem, CreditNote
from django.db.models import Sum, F
from decimal import Decimal
import datetime

today = datetime.date.today()
inv_qs = Invoice.objects.filter(status__in=['ISSUED', 'PAID'], creation_date__year=today.year, creation_date__month=today.month)

revenue_ex_vat = inv_qs.aggregate(Sum('subtotal_amount'))['subtotal_amount__sum'] or Decimal('0.00')
print("Total Overall Sales (subtotal_amount):", revenue_ex_vat)

credit_notes = CreditNote.objects.filter(original_invoice__in=inv_qs)
credit_subtotal = sum((cn.quantity * cn.unit_price) for cn in credit_notes)
print("Total Credits:", credit_subtotal)
print("Overall Sales Net:", float(revenue_ex_vat - Decimal(str(credit_subtotal))))

items = InvoiceItem.objects.filter(invoice__in=inv_qs)
gross = items.filter(product__category__icontains='Confectionery').annotate(ex=F('line_total')-F('tax_amount')).aggregate(Sum('ex'))['ex__sum'] or Decimal('0')
print("Confectionery Line Gross (Ex-VAT):", gross)

print("Invoices with custom discount:", inv_qs.filter(custom_discount_value__gt=0).count())

invoices = inv_qs.values('id', 'custom_discount_type', 'custom_discount_value')
inv_map = { i['id']: i for i in invoices }
items_dicts = items.values('invoice_id', 'product__category', 'product__name', 'quantity', 'unit_price', 'discount_type', 'discount')
inv_gross_sums = {}
processed_items = []
for item in items_dicts:
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
    processed_items.append({'item': item, 'gross': item_gross, 'inv_id': inv_id})

cat_sums = {'confectionery': Decimal('0.0'), 'sugar': Decimal('0.0'), 'creamer': Decimal('0.0'), 'tea': Decimal('0.0'), 'other': Decimal('0.0')}
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
    cat = (p_item['item']['product__category'] or '').lower()
    name = (p_item['item']['product__name'] or '').lower()
    if 'confectionery' in cat:
        cat_sums['confectionery'] += final_val
    elif 'sugar' in cat or 'sugar' in name:
        cat_sums['sugar'] += final_val
    elif 'creamer' in cat or 'creamer' in name:
        cat_sums['creamer'] += final_val
    elif 'tea' in cat or 'tea' in name:
        cat_sums['tea'] += final_val
    else:
        cat_sums['other'] += final_val

print("Python Logic Cat Sums:", {k: float(v) for k, v in cat_sums.items()})
print("Total Sum of Cat Sums:", sum(cat_sums.values()))

