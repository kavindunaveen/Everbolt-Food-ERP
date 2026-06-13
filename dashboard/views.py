from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from decimal import Decimal
from collections import defaultdict

from sales.models import Invoice, InvoiceItem
from crm.models import Customer
from inventory.models import Product
from .models import SalesTarget, ProductTargetGroup, ProductTarget, SalespersonTarget
from django.contrib.auth import get_user_model

User = get_user_model()


def get_target_value_rs(pt_qs):
    """
    Helper to convert ProductTarget quantity targets to Rupees (ex-VAT).
    For each ProductTarget in the queryset:
      value_rs = target_qty * (average unit selling price of the target group's products)
    """
    total_rs = 0.0
    for pt in pt_qs.select_related('target_group').prefetch_related('target_group__products'):
        products = list(pt.target_group.products.all())
        if not products:
            continue
        avg_price = sum(float(p.selling_price) for p in products) / len(products)
        total_rs += float(pt.target_value) * avg_price
    return total_rs


# ---------------------------------------------------------------------------
# Confectionery sub-product keyword mapping
# Each key is the canonical label shown in charts; value is a list of
# case-insensitive substrings that identify the product in product.name.
# Order matters — more specific keywords must come before broader ones.
# ---------------------------------------------------------------------------
CONFEC_BUCKETS = [
    ("Nescafe",     ["nescafe", "nescafé"]),
    ("Coffee Mate", ["coffee mate", "coffeemate"]),
    ("Catering Tea",["catering tea"]),
    ("Green Tea",   ["green tea"]),
    ("Flavored Tea",  ["flavored tea", "flavoured tea"]),
    ("Tea",         ["tea"]),
    ("Creamer",     ["creamer", "cream"]),
    ("Sugar",       ["sugar"]),
    ("Salt",        ["salt"]),
    ("Dried",       ["dried"]),
]

def classify_product(name: str) -> str | None:
    """Return bucket label for a product name, or None if not confectionery."""
    name_lower = name.lower()
    for label, keywords in CONFEC_BUCKETS:
        if any(kw in name_lower for kw in keywords):
            return label
    return None

class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'SalesDashboard'
        
        today = timezone.now().date()
        months = []
        for i in range(12):
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            import calendar
            start = timezone.datetime(year, month, 1).date()
            end = timezone.datetime(year, month, calendar.monthrange(year, month)[1]).date()
            months.append({
                'label': start.strftime('%b %Y'),
                'date_from': start.strftime('%Y-%m-%d'),
                'date_to': end.strftime('%Y-%m-%d'),
            })
        context['quick_months'] = months
        return context

class DashboardDataAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        import calendar
        date_from_raw = request.GET.get('date_from')
        date_to_raw = request.GET.get('date_to')
        
        target_year = timezone.now().year
        target_month = timezone.now().month
        using_custom_dates = False

        # Base invoices query
        inv_qs = Invoice.objects.filter(status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID])

        if request.GET.get('all_time') == 'true':
            using_custom_dates = True
        elif date_from_raw and date_to_raw:
            try:
                date_from = timezone.datetime.strptime(date_from_raw, '%Y-%m-%d').date()
                date_to = timezone.datetime.strptime(date_to_raw, '%Y-%m-%d').date()
                inv_qs = inv_qs.filter(creation_date__date__gte=date_from, creation_date__date__lte=date_to)
                
                last_day = calendar.monthrange(date_from.year, date_from.month)[1]
                if date_from.day == 1 and date_to.month == date_from.month and date_to.year == date_from.year and date_to.day == last_day:
                    target_year = date_from.year
                    target_month = date_from.month
                else:
                    using_custom_dates = True
                    target_year = date_from.year
                    target_month = date_from.month
            except ValueError:
                pass
        else:
            inv_qs = inv_qs.filter(creation_date__year=target_year, creation_date__month=target_month)

        invoice_items = InvoiceItem.objects.filter(invoice__in=inv_qs)

        # Overview Metrics
        total_invoices = inv_qs.count()
        total_customers = inv_qs.values('customer').distinct().count()
        total_packs = invoice_items.filter(product__stock_unit='pack').aggregate(Sum('quantity'))['quantity__sum'] or 0

        # Calculate precise Overall Sales (Ex-VAT) taking into account invoice-level discounts and credit notes
        from decimal import Decimal
        revenue_ex_vat = inv_qs.annotate(inv_ex_vat=F('total_amount') - F('tax_amount')).aggregate(Sum('inv_ex_vat'))['inv_ex_vat__sum'] or Decimal('0.00')
        from sales.models import CreditNoteItem
        cn_items = CreditNoteItem.objects.filter(credit_note__original_invoice__in=inv_qs)
        credit_subtotal = cn_items.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        overall_sales_total = float(revenue_ex_vat - Decimal(str(credit_subtotal)))
        
        # Calculate Category Sales Accurately (Handling Global Discounts)
        # We fetch necessary invoice and item data to proportionally apply global discounts
        invoices = inv_qs.values('id', 'custom_discount_type', 'custom_discount_value')
        inv_map = { i['id']: i for i in invoices }
        
        items = InvoiceItem.objects.filter(invoice__in=inv_qs).values(
            'invoice_id', 'product__category', 'product__name', 'quantity', 'unit_price', 'discount_type', 'discount'
        )
        
        # First pass: calculate gross ex-vat per item and sum per invoice
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
            
        # Second pass: apply global discount and sum by category
        cat_sums = {'confectionery': Decimal('0.0'), 'sugar': Decimal('0.0'), 'creamer': Decimal('0.0'), 'tea': Decimal('0.0')}
        
        for p_item in processed_items:
            inv = inv_map[p_item['inv_id']]
            inv_gross = inv_gross_sums[p_item['inv_id']]
            item_gross = p_item['gross']
            
            # Apply global discount
            c_type = inv['custom_discount_type']
            c_val = Decimal(str(inv['custom_discount_value'] or 0))
            
            if c_type == 'PERCENT':
                final_val = item_gross * (Decimal('1.0') - (c_val / Decimal('100.0')))
            else:
                # AMOUNT
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

        conf_credits = cn_items.filter(product__category__icontains='Confectionery').aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        confectionery_sales = float(cat_sums['confectionery'] - Decimal(str(conf_credits)))

        sugar_qty   = InvoiceItem.objects.filter(invoice__in=inv_qs).filter(Q(product__category__icontains='Sugar') | Q(product__name__icontains='Sugar')).aggregate(Sum('quantity'))['quantity__sum'] or 0
        sugar_credits = cn_items.filter(Q(product__category__icontains='Sugar') | Q(product__name__icontains='Sugar')).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        sugar_sales = float(cat_sums['sugar'] - Decimal(str(sugar_credits)))

        creamer_qty   = InvoiceItem.objects.filter(invoice__in=inv_qs).filter(Q(product__category__icontains='Creamer') | Q(product__name__icontains='Creamer')).aggregate(Sum('quantity'))['quantity__sum'] or 0
        creamer_credits = cn_items.filter(Q(product__category__icontains='Creamer') | Q(product__name__icontains='Creamer')).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        creamer_sales = float(cat_sums['creamer'] - Decimal(str(creamer_credits)))

        tea_qty   = InvoiceItem.objects.filter(invoice__in=inv_qs).filter(Q(product__category__icontains='Tea') | Q(product__name__icontains='Tea')).aggregate(Sum('quantity'))['quantity__sum'] or 0
        tea_credits = cn_items.filter(Q(product__category__icontains='Tea') | Q(product__name__icontains='Tea')).aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        tea_sales = float(cat_sums['tea'] - Decimal(str(tea_credits)))

        # Monthly Trends (always show full year trend regardless of month filter)
        all_items_year = InvoiceItem.objects.filter(
            invoice__creation_date__year=target_year,
            invoice__status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        ).select_related('invoice')
        months_names = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"]
        trend_data = {
            'months': months_names,
            'sugar_sales': [0] * 12, 'sugar_qty': [0] * 12,
            'creamer_sales': [0] * 12, 'creamer_qty': [0] * 12,
            'tea_sales': [0] * 12, 'tea_qty': [0] * 12,
            'overall_sales': [0] * 12,
        }
        
        # Calculate exactly like the overview
        y_invoices = Invoice.objects.filter(
            creation_date__year=target_year,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        ).values('id', 'custom_discount_type', 'custom_discount_value')
        y_inv_map = { i['id']: i for i in y_invoices }
        
        y_items = all_items_year.values(
            'invoice_id', 'invoice__creation_date__month', 'product__category', 'product__name', 'quantity', 'unit_price', 'discount_type', 'discount'
        )
        
        y_inv_gross_sums = {}
        y_processed_items = []
        for item in y_items:
            q = Decimal(str(item['quantity']))
            p = Decimal(str(item['unit_price']))
            d_val = Decimal(str(item['discount'] or 0))
            if item['discount_type'] == 'PERCENT':
                line_disc = (q * p) * (d_val / Decimal('100.0'))
            else:
                line_disc = d_val
                
            item_gross = (q * p) - line_disc
            inv_id = item['invoice_id']
            y_inv_gross_sums[inv_id] = y_inv_gross_sums.get(inv_id, Decimal('0.00')) + item_gross
            
            y_processed_items.append({
                'item': item,
                'gross': item_gross,
                'inv_id': inv_id
            })
            
        for p_item in y_processed_items:
            item = p_item['item']
            inv = y_inv_map[p_item['inv_id']]
            inv_gross = y_inv_gross_sums[p_item['inv_id']]
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
                    
            m_idx  = item['invoice__creation_date__month'] - 1
            c_name = (item['product__category'] or '').lower()
            p_name = (item['product__name'] or '').lower()
            val_s  = float(final_val)
            val_q  = float(item['quantity'])
            
            trend_data['overall_sales'][m_idx] += val_s
            if 'sugar' in c_name or 'sugar' in p_name:
                trend_data['sugar_sales'][m_idx] += val_s
                trend_data['sugar_qty'][m_idx]   += val_q
            elif 'creamer' in c_name or 'creamer' in p_name:
                trend_data['creamer_sales'][m_idx] += val_s
                trend_data['creamer_qty'][m_idx]   += val_q
            elif 'tea' in c_name or 'tea' in p_name:
                trend_data['tea_sales'][m_idx] += val_s
                trend_data['tea_qty'][m_idx]   += val_q

        # -------------------------------------------------------------------
        # Targets — month-aware
        # If using_custom_dates is True, targets are hidden.
        # -------------------------------------------------------------------
        def _get_targets(for_year, for_month):
            if using_custom_dates:
                return {
                    "overall": 0, "sugar": 0, "creamer": 0, "tea": 0, "has_target": False
                }

            sugar_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='sugar') | Q(target_group__products__name__icontains='sugar') | Q(target_group__name__icontains='sugar'),
                year=for_year, month=for_month
            ).distinct()
            sugar_t = sum(float(pt.target_value) for pt in sugar_qs)

            creamer_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='creamer') | Q(target_group__products__name__icontains='creamer') | Q(target_group__name__icontains='creamer'),
                year=for_year, month=for_month
            ).distinct()
            creamer_t = sum(float(pt.target_value) for pt in creamer_qs)

            tea_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='tea') | Q(target_group__name__icontains='tea'),
                year=for_year, month=for_month
            ).exclude(
                Q(target_group__products__name__icontains='catering tea') | Q(target_group__name__icontains='catering tea')
            ).distinct()
            tea_t = sum(float(pt.target_value) for pt in tea_qs)

            from dashboard.models import SalesTarget
            try:
                st = SalesTarget.objects.get(year=for_year, month=for_month, target_type='OVERALL_SALES')
                overall_t = float(st.target_value)
            except SalesTarget.DoesNotExist:
                overall_t = 0.0

            has_target = ProductTarget.objects.filter(year=for_year, month=for_month).exists()

            return {
                "overall": overall_t,
                "sugar": sugar_t,
                "creamer": creamer_t,
                "tea": tea_t,
                "has_target": has_target
            }

        target_dict = _get_targets(target_year, target_month)

        # ── Target achievement list by product category ──────────────────
        def _get_pct(achieved, target):
            return round((achieved / target) * 100, 2) if target > 0 else 0.0

        achievement_rows = []
        for group in ProductTargetGroup.objects.all().prefetch_related('products'):
            products = list(group.products.all())
            if not products:
                group_sales = 0.0
                achieved_qty = 0.0
            else:
                # Use two-pass Python discount logic for accurate group sales
                group_item_ids = [p.id for p in products]
                g_items = InvoiceItem.objects.filter(invoice__in=inv_qs, product__in=products).values(
                    'invoice_id', 'quantity', 'unit_price', 'discount_type', 'discount'
                )
                g_inv_gross_sums = {}
                g_processed = []
                for gi in g_items:
                    q = Decimal(str(gi['quantity']))
                    p = Decimal(str(gi['unit_price']))
                    d_val = Decimal(str(gi['discount'] or 0))
                    if gi['discount_type'] == 'PERCENT':
                        line_disc = (q * p) * (d_val / Decimal('100.0'))
                    else:
                        line_disc = d_val
                    item_gross = (q * p) - line_disc
                    inv_id = gi['invoice_id']
                    g_inv_gross_sums[inv_id] = g_inv_gross_sums.get(inv_id, Decimal('0.00')) + item_gross
                    g_processed.append({'gross': item_gross, 'inv_id': inv_id, 'qty': gi['quantity']})

                group_sales = 0.0
                achieved_qty = 0.0
                for gp in g_processed:
                    gi_inv = inv_map.get(gp['inv_id'])
                    if not gi_inv:
                        continue
                    inv_gross = inv_gross_sums.get(gp['inv_id'], Decimal('0.00'))
                    item_gross = gp['gross']
                    c_type = gi_inv['custom_discount_type']
                    c_val = Decimal(str(gi_inv['custom_discount_value'] or 0))
                    if c_type == 'PERCENT':
                        final_val = item_gross * (Decimal('1.0') - (c_val / Decimal('100.0')))
                    else:
                        if inv_gross > 0:
                            ratio = item_gross / inv_gross
                            final_val = item_gross - (ratio * c_val)
                        else:
                            final_val = item_gross
                    group_sales += float(final_val)
                    achieved_qty += float(gp['qty'])

            if using_custom_dates:
                target_qty = 0.0
            else:
                group_targets = ProductTarget.objects.filter(target_group=group, year=target_year, month=target_month)
                target_qty = float(group_targets.aggregate(s=Sum('target_value'))['s'] or 0)
            
            achievement_rows.append({
                'category': group.name,
                'sales': group_sales,
                'achieved_qty': achieved_qty,
                'target': target_qty,
                'pct': _get_pct(achieved_qty, target_qty),
                'has_target': not using_custom_dates and target_qty > 0
            })


        data = {
            "month": target_month if not using_custom_dates else None,
            "overview": {
                "total_invoices":      total_invoices,
                "total_customers":     total_customers,
                "total_packs":         float(total_packs),
                "confectionery_sales": float(confectionery_sales),
                "overall_sales_total": float(overall_sales_total),
                "sugar_qty":    float(sugar_qty),
                "sugar_sales":  float(sugar_sales),
                "creamer_qty":  float(creamer_qty),
                "creamer_sales":float(creamer_sales),
                "tea_qty":  float(tea_qty),
                "tea_sales":float(tea_sales),
            },
            "trends": trend_data,
            "targets": target_dict,
            "category_achievement": achievement_rows,
        }
        return JsonResponse(data)


class ConfectioneryAnalyticsAPI(LoginRequiredMixin, View):
    """
    Returns confectionery-specific analytics for 3 charts:
      1. sub_product_totals  – sales & qty per sub-product (Sugar, Creamer, Tea, …)
      2. by_customer         – stacked confectionery sales per customer name
      3. by_month            – total confectionery sales per calendar month
    """

    def get(self, request, *args, **kwargs):
        date_from_raw = request.GET.get('date_from')
        date_to_raw = request.GET.get('date_to')

        target_year = timezone.now().year
        target_month = timezone.now().month

        inv_qs = Invoice.objects.filter(status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID])

        if request.GET.get('all_time') == 'true':
            pass
        elif date_from_raw and date_to_raw:
            try:
                date_from = timezone.datetime.strptime(date_from_raw, '%Y-%m-%d').date()
                date_to = timezone.datetime.strptime(date_to_raw, '%Y-%m-%d').date()
                inv_qs = inv_qs.filter(creation_date__date__gte=date_from, creation_date__date__lte=date_to)
                target_year = date_from.year
                target_month = date_from.month
            except ValueError:
                pass
        else:
            inv_qs = inv_qs.filter(creation_date__year=target_year, creation_date__month=target_month)

        invoices = inv_qs

        # Pull every confectionery item with raw fields needed for accurate discount calculation
        raw_items = (
            InvoiceItem.objects
            .filter(invoice__in=invoices, product__category__iexact='Confectionery')
            .values(
                'invoice_id',
                'product__name',
                'quantity',
                'unit_price',
                'discount_type',
                'discount',
                'invoice__customer__customer_name',
                'invoice__creation_date__month',
                'invoice__custom_discount_type',
                'invoice__custom_discount_value',
            )
        )

        # To apply global discounts proportionally we need the total gross per invoice
        # across ALL items (not just confectionery items), so fetch that separately.
        all_items_gross = (
            InvoiceItem.objects
            .filter(invoice__in=invoices)
            .values('invoice_id', 'quantity', 'unit_price', 'discount_type', 'discount')
        )
        inv_gross_sums = {}
        for row in all_items_gross:
            q = Decimal(str(row['quantity']))
            p = Decimal(str(row['unit_price']))
            d_val = Decimal(str(row['discount'] or 0))
            if row['discount_type'] == 'PERCENT':
                line_disc = (q * p) * (d_val / Decimal('100.0'))
            else:
                line_disc = d_val
            inv_gross_sums[row['invoice_id']] = inv_gross_sums.get(row['invoice_id'], Decimal('0.00')) + (q * p) - line_disc

        # ---------- accumulators ----------
        bucket_labels = [b[0] for b in CONFEC_BUCKETS]

        sub_sales  = defaultdict(float)   # label -> total ex-VAT sales
        sub_qty    = defaultdict(float)   # label -> total quantity

        # customer -> { label -> sales }
        cust_data  = defaultdict(lambda: defaultdict(float))

        # month index (0-11) -> sales
        month_sales = [0.0] * 12

        for row in raw_items:
            pname   = row['product__name'] or ''
            qty     = row['quantity'] or 0
            cust    = row['invoice__customer__customer_name'] or 'Unknown'
            m_idx   = (row['invoice__creation_date__month'] or 1) - 1  # 0-based

            # Calculate item gross (after item-level discount, before global)
            q = Decimal(str(qty))
            p = Decimal(str(row['unit_price']))
            d_val = Decimal(str(row['discount'] or 0))
            if row['discount_type'] == 'PERCENT':
                line_disc = (q * p) * (d_val / Decimal('100.0'))
            else:
                line_disc = d_val
            item_gross = (q * p) - line_disc

            # Apply proportional global discount
            inv_id = row['invoice_id']
            inv_gross = inv_gross_sums.get(inv_id, Decimal('0.00'))
            c_type = row['invoice__custom_discount_type']
            c_val = Decimal(str(row['invoice__custom_discount_value'] or 0))
            if c_type == 'PERCENT':
                final_val = item_gross * (Decimal('1.0') - (c_val / Decimal('100.0')))
            else:
                if inv_gross > 0:
                    ratio = item_gross / inv_gross
                    final_val = item_gross - (ratio * c_val)
                else:
                    final_val = item_gross

            exvat = float(final_val)

            label = classify_product(pname)
            if label is None:
                label = 'Other'

            sub_sales[label]  += exvat
            sub_qty[label]    += float(qty)
            cust_data[cust][label] += exvat
            month_sales[m_idx] += exvat


        # ---------- build response ----------

        # 1. Sub-product totals
        sub_product_totals = [
            {
                'label': lbl,
                'sales': round(sub_sales.get(lbl, 0.0), 2),
                'qty':   round(sub_qty.get(lbl, 0.0),   2),
            }
            for lbl in bucket_labels
        ]

        # 2. By-customer (top 30 customers by total confectionery sales)
        cust_totals = {
            cname: sum(vals.values())
            for cname, vals in cust_data.items()
        }
        top_customers = sorted(cust_totals, key=lambda c: cust_totals[c], reverse=True)[:30]

        by_customer = {
            'customers': top_customers,
            'datasets': [
                {
                    'label': lbl,
                    'data':  [round(cust_data[c].get(lbl, 0.0), 2) for c in top_customers],
                }
                for lbl in bucket_labels
            ],
        }

        # 3. By-month
        month_names = [
            "Jan", "Feb", "Mar", "Apr", "May", "Jun",
            "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"
        ]
        by_month = {
            'months': month_names,
            'sales':  [round(v, 2) for v in month_sales],
        }

        return JsonResponse({
            'year': target_year,
            'sub_product_totals': sub_product_totals,
            'by_customer': by_customer,
            'by_month': by_month,
        })


# ---------------------------------------------------------------------------
# Target Management — helpers
# ---------------------------------------------------------------------------
import calendar as _calendar
import json as _json
from django.contrib import messages
from django.shortcuts import redirect

CAT_ROWS = [
    {'label': 'Overall Sales', 'type': 'OVERALL_SALES',  'category': None,      'key': 'overall'},
    {'label': 'Sugar Sales',   'type': 'CATEGORY_SALES', 'category': 'Sugar',   'key': 'sugar'},
    {'label': 'Creamer Sales', 'type': 'CATEGORY_SALES', 'category': 'Creamer', 'key': 'creamer'},
    {'label': 'Tea Sales',     'type': 'CATEGORY_SALES', 'category': 'Tea',     'key': 'tea'},
]
MONTH_ABBR = [_calendar.month_abbr[m] for m in range(1, 13)]


def _check_target_access(request):
    return request.user.is_admin() or request.user.can_set_targets


def _upsert_category(year, target_type, category, month, val_str):
    val_str = (val_str or '').strip()
    if val_str:
        try:
            SalesTarget.objects.update_or_create(
                year=year, month=month, target_type=target_type, category=category,
                defaults={'target_value': float(val_str)}
            )
        except ValueError:
            pass
    else:
        SalesTarget.objects.filter(
            year=year, month=month, target_type=target_type, category=category
        ).delete()


def _upsert_group_target(group, year, month, val_str):
    val_str = (val_str or '').strip()
    if val_str:
        try:
            ProductTarget.objects.update_or_create(
                target_group=group, year=year, month=month,
                defaults={'target_value': float(val_str)}
            )
        except ValueError:
            pass
    else:
        ProductTarget.objects.filter(target_group=group, year=year, month=month).delete()


# ---------------------------------------------------------------------------
# Target Management View
# ---------------------------------------------------------------------------
class TargetManagementView(LoginRequiredMixin, View):
    template_name = 'dashboard/targets.html'

    def get(self, request, *args, **kwargs):
        if not _check_target_access(request):
            messages.error(request, "You don't have permission to manage targets.")
            return redirect('analytics_dashboard')

        year = int(request.GET.get('year', timezone.now().year))
        available_years = list(range(timezone.now().year + 1, 2022, -1))

        # ── Overall Company Target ────────────────────────────────────────────
        overall_existing = {}
        for st in SalesTarget.objects.filter(year=year, target_type=SalesTarget.TargetTypes.OVERALL_SALES):
            overall_existing[st.month] = float(st.target_value)
            
        overall_periods = []
        for m in range(1, 13):
            overall_periods.append({
                'field': f"overall_m{m}",
                'value': overall_existing.get(m, ''),
                'label': MONTH_ABBR[m - 1],
            })

        # ── Product Group target rows ─────────────────────────────────────────
        prod_existing = {}
        for pt in ProductTarget.objects.filter(year=year).select_related('target_group'):
            prod_existing[(pt.target_group_id, pt.month)] = float(pt.target_value)

        prod_rows = []
        for group in ProductTargetGroup.objects.prefetch_related('products').all():
            periods = []
            for m in range(1, 13):
                periods.append({
                    'field': f"gt_{group.id}_m{m}",
                    'value': prod_existing.get((group.id, m), ''),
                    'label': MONTH_ABBR[m - 1],
                })
            
            linked_products = [
                {'id': p.id, 'product_id': p.product_id, 'name': p.name, 'category': p.category}
                for p in group.products.all()
            ]
            
            prod_rows.append({
                'group_id': group.id,
                'name': group.name,
                'periods': periods,
                'products': linked_products,
            })

        # Fetch all available groups to allow adding products to them
        all_groups = [{'id': g.id, 'name': g.name} for g in ProductTargetGroup.objects.all()]

        # ── Salesperson target rows ───────────────────────────────────────────
        sp_existing = {}
        for spt in SalespersonTarget.objects.filter(year=year).select_related('salesperson'):
            sp_existing[(spt.salesperson_id, spt.month)] = float(spt.target_value)

        salesperson_rows = []
        for sp in User.objects.filter(role__name='Sales Officer').order_by('username'):
            periods = []
            for m in range(1, 13):
                periods.append({
                    'field': f"st_{sp.id}_m{m}",
                    'value': sp_existing.get((sp.id, m), ''),
                    'label': MONTH_ABBR[m - 1],
                })
            salesperson_rows.append({
                'id': sp.id,
                'name': f"{sp.first_name} {sp.last_name} ({sp.username})",
                'periods': periods,
            })

        return render(request, self.template_name, {
            'overall_periods': overall_periods,
            'prod_rows': prod_rows,
            'salesperson_rows': salesperson_rows,
            'all_groups': all_groups,
            'year': year,
            'available_years': available_years,
            'month_abbr': MONTH_ABBR,
        })

    def post(self, request, *args, **kwargs):
        if not _check_target_access(request):
            return JsonResponse({'error': 'Forbidden'}, status=403)

        action = request.POST.get('action', 'save_targets')
        year = int(request.POST.get('year', timezone.now().year))

        if action == 'create_group':
            name = request.POST.get('name', '').strip()
            if not name:
                return JsonResponse({'error': 'Group name is required'}, status=400)
            
            if ProductTargetGroup.objects.filter(name__iexact=name).exists():
                return JsonResponse({'error': f'Group "{name}" already exists'}, status=400)

            group = ProductTargetGroup.objects.create(
                name=name,
                display_order=ProductTargetGroup.objects.count()
            )
            return JsonResponse({
                'status': 'ok',
                'group_id': group.id,
                'name': group.name
            })

        if action == 'add_product':
            pid = request.POST.get('product_db_id')
            gid = request.POST.get('group_id')
            try:
                product = Product.objects.get(pk=pid)
                if gid:
                    group = ProductTargetGroup.objects.get(pk=gid)
                else:
                    gname = product.name
                    base_gname = gname
                    counter = 1
                    while ProductTargetGroup.objects.filter(name__iexact=gname).exists():
                        gname = f"{base_gname} ({counter})"
                        counter += 1
                    group = ProductTargetGroup.objects.create(
                        name=gname,
                        display_order=ProductTargetGroup.objects.count()
                    )
                
                group.products.add(product)
                
                linked_products = [
                    {'id': p.id, 'product_id': p.product_id, 'name': p.name, 'category': p.category}
                    for p in group.products.all()
                ]
                
                return JsonResponse({
                    'status': 'ok',
                    'group_id': group.id,
                    'name': group.name,
                    'products': linked_products
                })
            except Product.DoesNotExist:
                return JsonResponse({'error': 'Product not found'}, status=404)
            except ProductTargetGroup.DoesNotExist:
                return JsonResponse({'error': 'Group not found'}, status=404)

        if action == 'remove_product':
            gid = request.POST.get('group_id')
            pid = request.POST.get('product_db_id')
            try:
                group = ProductTargetGroup.objects.get(pk=gid)
                product = Product.objects.get(pk=pid)
                group.products.remove(product)
                
                if group.products.count() == 0:
                    group.delete()
                    return JsonResponse({'status': 'ok', 'group_deleted': True})
                    
                return JsonResponse({
                    'status': 'ok',
                    'group_deleted': False,
                    'products': [
                        {'id': p.id, 'product_id': p.product_id, 'name': p.name, 'category': p.category}
                        for p in group.products.all()
                    ]
                })
            except (ProductTargetGroup.DoesNotExist, Product.DoesNotExist):
                return JsonResponse({'error': 'Not found'}, status=404)

        if action == 'delete_group':
            gid = request.POST.get('group_id')
            try:
                group = ProductTargetGroup.objects.get(pk=gid)
                group.delete()
                return JsonResponse({'status': 'ok'})
            except ProductTargetGroup.DoesNotExist:
                return JsonResponse({'error': 'Not found'}, status=404)

        for m in range(1, 13):
            _upsert_category(year, SalesTarget.TargetTypes.OVERALL_SALES, None, m, request.POST.get(f"overall_m{m}"))

        for group in ProductTargetGroup.objects.all():
            for m in range(1, 13):
                _upsert_group_target(group, year, m, request.POST.get(f"gt_{group.id}_m{m}"))

        for sp in User.objects.filter(role__name='Sales Officer'):
            for m in range(1, 13):
                val_str = (request.POST.get(f"st_{sp.id}_m{m}") or '').strip()
                if val_str:
                    try:
                        SalespersonTarget.objects.update_or_create(
                            salesperson=sp, year=year, month=m,
                            defaults={'target_value': float(val_str)}
                        )
                    except ValueError:
                        pass
                else:
                    SalespersonTarget.objects.filter(salesperson=sp, year=year, month=m).delete()

        from django.contrib import messages
        messages.success(request, f"Targets for {year} saved successfully.")
        return redirect(f"{request.path}?year={year}")


# ---------------------------------------------------------------------------
# Product Search API  — used by the autocomplete widget on the targets page
# GET /dashboard/api/product-search/?q=sugar
# ---------------------------------------------------------------------------
class ProductSearchAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        q = request.GET.get('q', '').strip()
        is_all = request.GET.get('all') == 'true'
        
        if len(q) < 2:
            return JsonResponse({'results': []})

        products_query = Product.objects.filter(
            Q(name__icontains=q) | Q(product_id__icontains=q),
            status=True,
        )

        if not is_all:
            # Exclude products already linked to a target group
            linked_pids = set(ProductTargetGroup.objects.values_list('products__id', flat=True))
            products_query = products_query.exclude(id__in=linked_pids)

        products = products_query.order_by('name')[:25]

        return JsonResponse({
            'results': [
                {'id': p.id, 'product_id': p.product_id,
                 'name': p.name, 'category': p.category}
                for p in products
            ]
        })


# ---------------------------------------------------------------------------
# Product Targets API  — feeds the dashboard Product Performance section
# GET /dashboard/api/product-targets/?year=2026&month=5
# ---------------------------------------------------------------------------
class ProductTargetsAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        import calendar
        date_from_raw = request.GET.get('date_from')
        date_to_raw = request.GET.get('date_to')

        target_year = timezone.now().year
        target_month = timezone.now().month
        using_custom_dates = False

        if request.GET.get('all_time') == 'true':
            using_custom_dates = True
        elif date_from_raw and date_to_raw:
            try:
                date_from = timezone.datetime.strptime(date_from_raw, '%Y-%m-%d').date()
                date_to = timezone.datetime.strptime(date_to_raw, '%Y-%m-%d').date()
                
                last_day = calendar.monthrange(date_from.year, date_from.month)[1]
                if date_from.day == 1 and date_to.month == date_from.month and date_to.year == date_from.year and date_to.day == last_day:
                    target_year = date_from.year
                    target_month = date_from.month
                else:
                    using_custom_dates = True
                    target_year = date_from.year
                    target_month = date_from.month
            except ValueError:
                pass

        STATUSES = [Invoice.Status.ISSUED, Invoice.Status.PAID]
        results = []

        for group in ProductTargetGroup.objects.prefetch_related('products').all():
            products_list = list(group.products.all())
            if not products_list:
                continue

            # ── Actual sales for selected period (with global discount) ──────
            items_qs = InvoiceItem.objects.filter(
                product__in=products_list,
                invoice__status__in=STATUSES,
            )
            if request.GET.get('all_time') == 'true':
                pass
            elif date_from_raw and date_to_raw and 'date_from' in locals() and 'date_to' in locals():
                items_qs = items_qs.filter(
                    invoice__creation_date__date__gte=date_from,
                    invoice__creation_date__date__lte=date_to
                )
            else:
                items_qs = items_qs.filter(
                    invoice__creation_date__year=target_year,
                    invoice__creation_date__month=target_month
                )

            # Two-pass: need per-invoice gross totals across ALL items (to prorate global discount)
            inv_ids_in_qs = list(items_qs.values_list('invoice_id', flat=True).distinct())
            all_inv_items = InvoiceItem.objects.filter(invoice_id__in=inv_ids_in_qs).values(
                'invoice_id', 'quantity', 'unit_price', 'discount_type', 'discount'
            )
            pt_inv_gross_sums = {}
            for ai in all_inv_items:
                q = Decimal(str(ai['quantity']))
                p = Decimal(str(ai['unit_price']))
                d_val = Decimal(str(ai['discount'] or 0))
                ld = (q * p) * (d_val / Decimal('100.0')) if ai['discount_type'] == 'PERCENT' else d_val
                pt_inv_gross_sums[ai['invoice_id']] = pt_inv_gross_sums.get(ai['invoice_id'], Decimal('0.00')) + (q * p) - ld

            inv_meta = {
                i['id']: i for i in
                Invoice.objects.filter(id__in=inv_ids_in_qs).values('id', 'custom_discount_type', 'custom_discount_value')
            }

            pt_items_raw = items_qs.values('invoice_id', 'quantity', 'unit_price', 'discount_type', 'discount')
            actual = 0.0
            actual_qty = 0.0
            for pi in pt_items_raw:
                q = Decimal(str(pi['quantity']))
                p = Decimal(str(pi['unit_price']))
                d_val = Decimal(str(pi['discount'] or 0))
                ld = (q * p) * (d_val / Decimal('100.0')) if pi['discount_type'] == 'PERCENT' else d_val
                item_gross = (q * p) - ld
                inv_id = pi['invoice_id']
                inv_gross = pt_inv_gross_sums.get(inv_id, Decimal('0.00'))
                inv_meta_row = inv_meta.get(inv_id, {})
                c_type = inv_meta_row.get('custom_discount_type', 'AMOUNT')
                c_val = Decimal(str(inv_meta_row.get('custom_discount_value') or 0))
                if c_type == 'PERCENT':
                    final_val = item_gross * (Decimal('1.0') - (c_val / Decimal('100.0')))
                else:
                    final_val = item_gross - ((item_gross / inv_gross) * c_val) if inv_gross > 0 else item_gross
                actual += float(final_val)
                actual_qty += float(pi['quantity'])

            # ── Target for this period ────────────────────────────────────
            if using_custom_dates:
                target_qty = 0.0
                has_target = False
            else:
                try:
                    pt = ProductTarget.objects.get(target_group=group, year=target_year, month=target_month)
                    target_qty = float(pt.target_value)
                    has_target = True
                except ProductTarget.DoesNotExist:
                    target_qty = 0.0
                    has_target = False

            pct = round(actual_qty / target_qty * 100, 1) if target_qty > 0 else 0

            # ── Monthly trend (always full 12 months) ─────────────────────
            all_year_raw = InvoiceItem.objects.filter(
                product__in=products_list,
                invoice__creation_date__year=target_year,
                invoice__status__in=STATUSES,
            ).values('invoice_id', 'invoice__creation_date__month', 'quantity', 'unit_price', 'discount_type', 'discount')

            # Need all-item grosses for the full year invoices as well
            year_inv_ids = list(set(r['invoice_id'] for r in all_year_raw))
            year_all_items = InvoiceItem.objects.filter(invoice_id__in=year_inv_ids).values(
                'invoice_id', 'quantity', 'unit_price', 'discount_type', 'discount'
            )
            year_inv_gross = {}
            for ai in year_all_items:
                q2 = Decimal(str(ai['quantity']))
                p2 = Decimal(str(ai['unit_price']))
                dv2 = Decimal(str(ai['discount'] or 0))
                ld2 = (q2 * p2) * (dv2 / Decimal('100.0')) if ai['discount_type'] == 'PERCENT' else dv2
                year_inv_gross[ai['invoice_id']] = year_inv_gross.get(ai['invoice_id'], Decimal('0.00')) + (q2 * p2) - ld2
            year_inv_meta = {
                i['id']: i for i in
                Invoice.objects.filter(id__in=year_inv_ids).values('id', 'custom_discount_type', 'custom_discount_value')
            }

            monthly_trend = [0.0] * 12
            for yr in all_year_raw:
                q2 = Decimal(str(yr['quantity']))
                p2 = Decimal(str(yr['unit_price']))
                dv2 = Decimal(str(yr['discount'] or 0))
                ld2 = (q2 * p2) * (dv2 / Decimal('100.0')) if yr['discount_type'] == 'PERCENT' else dv2
                ig2 = (q2 * p2) - ld2
                inv_id2 = yr['invoice_id']
                inv_gross2 = year_inv_gross.get(inv_id2, Decimal('0.00'))
                im2 = year_inv_meta.get(inv_id2, {})
                ct2 = im2.get('custom_discount_type', 'AMOUNT')
                cv2 = Decimal(str(im2.get('custom_discount_value') or 0))
                if ct2 == 'PERCENT':
                    fv2 = ig2 * (Decimal('1.0') - (cv2 / Decimal('100.0')))
                else:
                    fv2 = ig2 - ((ig2 / inv_gross2) * cv2) if inv_gross2 > 0 else ig2
                m_idx2 = yr['invoice__creation_date__month'] - 1
                monthly_trend[m_idx2] = round(monthly_trend[m_idx2] + float(fv2), 2)


            # ── Monthly targets ───────────────────────────────────────────
            monthly_targets = [0.0] * 12
            for pt_m in ProductTarget.objects.filter(target_group=group, year=target_year,
                                                     month__isnull=False):
                monthly_targets[pt_m.month - 1] = float(pt_m.target_value)

            results.append({
                'group_id':     group.id,
                'product_codes': ", ".join([p.product_id for p in products_list]),
                'name':         group.name,
                'category':     ", ".join(sorted(list(set([p.category for p in products_list])))),
                'actual_sales': actual,
                'actual_qty':   actual_qty,
                'target_value': target_qty,
                'has_target':   has_target,
                'pct_achieved': pct,
                'monthly_trend':   monthly_trend,
                'monthly_targets': monthly_targets,
            })

        return JsonResponse({'year': target_year, 'month': target_month if not using_custom_dates else None, 'products': results})

from django.db.models.functions import TruncDate
from datetime import date, timedelta
from .models import ForecastingSettings

class ForecastingView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/forecasting.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localtime().date()
        target_year = today.year
        target_month = today.month

        # Get settings
        settings, created = ForecastingSettings.objects.get_or_create(
            year=target_year, month=target_month,
            defaults={'milestone_target': 500000, 'total_working_days': 25}
        )
        context['settings'] = settings

        # 1. Overall Target & Manual Daily Target
        overall_target_val = 0
        try:
            st = SalesTarget.objects.get(year=target_year, month=target_month, target_type='OVERALL_SALES')
            overall_target_val = float(st.target_value)
        except SalesTarget.DoesNotExist:
            pass
        
        context['overall_target'] = overall_target_val
        context['manual_daily_target'] = overall_target_val / settings.total_working_days if settings.total_working_days > 0 else 0

        # 2. Working Days Passed & Actual Pace
        days_passed = 0
        for d in range(1, today.day + 1):
            date_obj = date(today.year, today.month, d)
            if date_obj.weekday() != 6:  # 6 is Sunday
                days_passed += 1
        
        context['working_days_passed'] = days_passed

        # Total Net Sales this month (subtract credit notes for accuracy)
        inv_this_month = Invoice.objects.filter(
            creation_date__year=target_year,
            creation_date__month=target_month,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        ).annotate(ex_vat=F('total_amount') - F('tax_amount'))
        from decimal import Decimal
        total_sales_gross = inv_this_month.aggregate(total=Sum('ex_vat'))['total'] or Decimal('0.00')
        
        from sales.models import CreditNoteItem
        cn_items = CreditNoteItem.objects.filter(credit_note__original_invoice__in=inv_this_month)
        credit_subtotal = cn_items.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        
        total_sales = float(total_sales_gross - Decimal(str(credit_subtotal)))
        context['total_sales'] = total_sales
        actual_pace = total_sales / days_passed if days_passed > 0 else 0
        context['actual_pace'] = actual_pace

        # 05. Work Days Remaining
        working_days_remaining = max(0, settings.total_working_days - days_passed)
        context['working_days_remaining'] = working_days_remaining

        # 08. Target Achieved Percentage
        target_achieved_pct = (context['total_sales'] / overall_target_val * 100) if overall_target_val else 0
        context['target_achieved_pct'] = target_achieved_pct

        # 09. Remaining Target Percentage
        context['remaining_target_pct'] = max(0, 100 - target_achieved_pct) if overall_target_val else 0

        # 11. Remaining Sales Amount
        remaining_sales_amount = max(0, overall_target_val - context['total_sales'])
        context['remaining_sales_amount'] = remaining_sales_amount

        # 10. Required Daily Sales for Remaining Days
        context['req_daily_sales_remaining'] = remaining_sales_amount / working_days_remaining if working_days_remaining > 0 else 0

        # 06. Projected Month-End Sales
        # Using the specific requested formula for projection but using actual_pace to make the dynamic "go by this pace" math work.
        projected_sales = context['total_sales'] + (working_days_remaining * actual_pace)
        context['projected_sales'] = projected_sales

        # 12. Shortfall Against Target
        shortfall = max(0, overall_target_val - projected_sales)
        context['shortfall'] = shortfall

        # 13. Target Status
        context['target_status'] = "ON TRACK" if projected_sales >= overall_target_val else "FALLING SHORT"

        # 3. Top Performer
        top_performer = inv_this_month.values(
            'salesperson__first_name', 'salesperson__last_name', 'salesperson__username'
        ).annotate(total_revenue=Sum('ex_vat')).order_by('-total_revenue').first()
        context['top_performer'] = top_performer

        # 4. Milestone Speed Calculation & Risk
        daily_sales = inv_this_month.annotate(date_only=TruncDate('creation_date')).values('date_only').annotate(daily_total=Sum('ex_vat')).order_by('date_only')
        
        milestones = []
        cumulative = 0
        current_milestone_target = float(settings.milestone_target)
        prev_milestone_date = date(target_year, target_month, 1) - timedelta(days=1)
        
        if current_milestone_target > 0:
            for day_data in daily_sales:
                day_date = day_data['date_only']
                daily_val = float(day_data['daily_total'] or 0)
                cumulative += daily_val
                
                while cumulative >= current_milestone_target:
                    # Calculate working days taken since last milestone
                    days_taken = 0
                    curr_date = prev_milestone_date + timedelta(days=1)
                    while curr_date <= day_date:
                        if curr_date.weekday() != 6: # Exclude Sunday
                            days_taken += 1
                        curr_date += timedelta(days=1)
                    
                    # If days_taken is 0 (e.g. hit two milestones in one day), treat as 1 for division/display if needed, or just 0
                    
                    milestones.append({
                        'target': current_milestone_target,
                        'date_reached': day_date,
                        'days_taken': days_taken,
                        'status': 'Risk' if days_taken >= 5 else 'Good speed'
                    })
                    
                    prev_milestone_date = day_date
                    current_milestone_target += float(settings.milestone_target)
                    
        context['milestones'] = milestones

        # 5. Monthly Comparison Chart Data
        # Calculate days in the target month
        import calendar
        _, num_days = calendar.monthrange(target_year, target_month)
        
        # We need cumulative actual sales up to today (if current month) or end of month (if past month)
        chart_labels = list(range(1, num_days + 1))
        
        cumulative_actual = []
        current_cumulative = 0
        
        # Convert daily_sales to a dictionary for O(1) lookup
        daily_sales_dict = {d['date_only'].day: float(d['daily_total'] or 0) for d in daily_sales}
        
        max_day = today.day if (target_year == today.year and target_month == today.month) else num_days
        
        for day in range(1, max_day + 1):
            current_cumulative += daily_sales_dict.get(day, 0)
            cumulative_actual.append(current_cumulative)

        # Calculate cumulative target line (Linear progression of overall target)
        cumulative_target = []
        if overall_target_val > 0:
            daily_linear_target = overall_target_val / num_days
            for day in range(1, num_days + 1):
                cumulative_target.append(round(daily_linear_target * day, 2))
        
        import json
        context['chart_labels_json'] = json.dumps(chart_labels)
        context['chart_actual_sales_json'] = json.dumps(cumulative_actual)
        context['chart_target_sales_json'] = json.dumps(cumulative_target)
        
        # 5. Month-by-Month Comparison
        last_month = target_month - 1
        last_month_year = target_year
        if last_month == 0:
            last_month = 12
            last_month_year -= 1
            
        inv_last_month = Invoice.objects.filter(
            creation_date__year=last_month_year,
            creation_date__month=last_month,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        ).annotate(ex_vat=F('total_amount') - F('tax_amount'))
        
        total_sales_last_month = inv_last_month.aggregate(total=Sum('ex_vat'))['total'] or 0
        context['total_sales_last_month'] = float(total_sales_last_month)
        
        # Overall difference
        diff = float(total_sales) - context['total_sales_last_month']
        context['total_sales_diff'] = diff
        context['abs_total_sales_diff'] = abs(diff)
        if context['total_sales_last_month'] > 0:
            context['total_sales_pct'] = (diff / context['total_sales_last_month']) * 100
        else:
            context['total_sales_pct'] = 100.0 if float(total_sales) > 0 else 0.0
        
        # Calculate last month cumulative sales for chart
        daily_sales_last_month = inv_last_month.annotate(date_only=TruncDate('creation_date')).values('date_only').annotate(daily_total=Sum('ex_vat'))
        daily_sales_dict_last_month = {d['date_only'].day: float(d['daily_total'] or 0) for d in daily_sales_last_month}
        
        cumulative_last = []
        current_cumulative_last = 0
        _, num_days_last = calendar.monthrange(last_month_year, last_month)
        
        for day in range(1, num_days + 1):
            if day <= num_days_last:
                current_cumulative_last += daily_sales_dict_last_month.get(day, 0)
            cumulative_last.append(current_cumulative_last)
            
        context['chart_last_month_sales_json'] = json.dumps(cumulative_last)
        
        # Product Comparison (Advanced)
        from sales.models import InvoiceItem
        
        def get_advanced_product_sales(inv_qs):
            # Same reliable python processing
            invoices = inv_qs.values('id', 'custom_discount_type', 'custom_discount_value')
            inv_map = { i['id']: i for i in invoices }
            
            items = InvoiceItem.objects.filter(invoice__in=inv_qs).values(
                'invoice_id', 'product__name', 'quantity', 'unit_price', 'discount_type', 'discount', 'invoice__creation_date'
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
                
            results = {}
            daily_results = {}
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
                        
                name = p_item['item']['product__name']
                q = p_item['item']['quantity']
                
                if name not in results:
                    results[name] = {'product__name': name, 'total_revenue': Decimal('0.00'), 'total_qty': 0}
                results[name]['total_revenue'] += final_val
                results[name]['total_qty'] += q
                
                date_only = p_item['item']['invoice__creation_date'].date()
                d_key = (name, date_only)
                daily_results[d_key] = daily_results.get(d_key, Decimal('0.00')) + final_val
                
            return list(results.values()), daily_results
            
        curr_qs, curr_daily = get_advanced_product_sales(inv_this_month)
        curr_prod_sales = {item['product__name']: item for item in curr_qs}
        
        last_qs, last_daily = get_advanced_product_sales(inv_last_month)
        last_prod_sales = {item['product__name']: item for item in last_qs}
        
        sparkline_dict = {}
        for (prod_name, date_only), rev in curr_daily.items():
            if prod_name:
                day = date_only.day
                if prod_name not in sparkline_dict:
                    sparkline_dict[prod_name] = {}
                if day <= max_day:
                    sparkline_dict[prod_name][day] = float(rev)
        
        prod_comparison = []
        all_prods = set([k for k in curr_prod_sales.keys() if k]).union(set([k for k in last_prod_sales.keys() if k]))
        
        for p in all_prods:
            c_val = float(curr_prod_sales.get(p, {}).get('total_revenue', 0) or 0)
            c_qty = float(curr_prod_sales.get(p, {}).get('total_qty', 0) or 0)
            l_val = float(last_prod_sales.get(p, {}).get('total_revenue', 0) or 0)
            l_qty = float(last_prod_sales.get(p, {}).get('total_qty', 0) or 0)
            diff = c_val - l_val
            pct = (diff / l_val * 100) if l_val > 0 else (100 if c_val > 0 else 0)
            
            sparkline_data = [sparkline_dict.get(p, {}).get(i, 0) for i in range(1, max_day + 1)]
            
            prod_comparison.append({
                'name': p,
                'current': c_val,
                'current_qty': c_qty,
                'last': l_val,
                'last_qty': l_qty,
                'diff': diff,
                'pct': pct,
                'sparkline_json': json.dumps(sparkline_data)
            })
            
        prod_comparison.sort(key=lambda x: x['current'], reverse=True)
        context['product_comparison'] = prod_comparison[:10]

        import calendar
        context['target_month_name'] = calendar.month_name[target_month]
        return context

class ForecastingSettingsView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        from django.shortcuts import redirect
        from django.contrib import messages
        today = timezone.localtime().date()
        settings, _ = ForecastingSettings.objects.get_or_create(
            year=today.year, month=today.month
        )
        try:
            settings.milestone_target = float(request.POST.get('milestone_target', 500000))
            settings.total_working_days = int(request.POST.get('total_working_days', 25))
            settings.save()
            messages.success(request, "Forecasting settings updated successfully.")
        except Exception as e:
            messages.error(request, f"Error saving settings: {e}")
        return redirect('forecasting')

from .models import CompanySettings
from .forms import CompanySettingsForm

class CompanySettingsView(LoginRequiredMixin, View):
    def get(self, request):
        if not request.user.is_superuser:
            messages.error(request, "Only administrators can access company settings.")
            return redirect('analytics_dashboard')
            
        settings_obj, created = CompanySettings.objects.get_or_create(id=1)
        form = CompanySettingsForm(instance=settings_obj)
        return render(request, 'dashboard/settings.html', {'form': form, 'settings': settings_obj})

    def post(self, request):
        if not request.user.is_superuser:
            return redirect('analytics_dashboard')
            
        settings_obj, created = CompanySettings.objects.get_or_create(id=1)
        form = CompanySettingsForm(request.POST, request.FILES, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, "Company settings updated successfully.")
            return redirect('company_settings')
        
        return render(request, 'dashboard/settings.html', {'form': form, 'settings': settings_obj})

from sales.models import Quotation

class SalespersonDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'dashboard/salesperson_analytics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['model_name'] = 'SalespersonDashboard'
        
        # Determine if user can select other salespeople
        can_view_all = self.request.user.is_admin() or getattr(self.request.user, 'can_view_all_sales_performance', False)
        context['can_view_all'] = can_view_all
        
        if can_view_all:
            context['salespeople'] = User.objects.filter(is_active=True, role__name='Sales Officer').order_by('first_name', 'username')
        else:
            context['salespeople'] = [self.request.user]
            
        today = timezone.now().date()
        months = []
        for i in range(12):
            month = today.month - i
            year = today.year
            while month <= 0:
                month += 12
                year -= 1
            import calendar
            start = timezone.datetime(year, month, 1).date()
            end = timezone.datetime(year, month, calendar.monthrange(year, month)[1]).date()
            months.append({
                'label': start.strftime('%b %Y'),
                'date_from': start.strftime('%Y-%m-%d'),
                'date_to': end.strftime('%Y-%m-%d'),
            })
        context['quick_months'] = months
        
        from users.models import SavedFilter
        context['saved_filters'] = SavedFilter.objects.filter(user=self.request.user, model_name='SalespersonDashboard').order_by('-created_at')
        
        return context

class SalespersonDataAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        import calendar
        date_from_raw = request.GET.get('date_from')
        date_to_raw = request.GET.get('date_to')
        sp_id_raw = request.GET.get('salesperson_id')
        
        # Permission check
        can_view_all = request.user.is_admin() or getattr(request.user, 'can_view_all_sales_performance', False)
        if not can_view_all:
            sp_id = request.user.id
        else:
            try:
                sp_id = int(sp_id_raw) if sp_id_raw else request.user.id
            except ValueError:
                sp_id = request.user.id
                
        salesperson = User.objects.filter(id=sp_id).first()
        if not salesperson:
            return JsonResponse({'error': 'Salesperson not found'}, status=404)

        target_year = timezone.now().year
        target_month = timezone.now().month
        using_custom_dates = False
        is_current_month = False

        inv_qs = Invoice.objects.filter(status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID], salesperson=salesperson)
        quot_qs = Quotation.objects.filter(salesperson=salesperson)
        cust_qs = Customer.objects.filter(assigned_sales_officer=salesperson)

        if request.GET.get('all_time') == 'true':
            using_custom_dates = True
        elif date_from_raw and date_to_raw:
            try:
                date_from = timezone.datetime.strptime(date_from_raw, '%Y-%m-%d').date()
                date_to = timezone.datetime.strptime(date_to_raw, '%Y-%m-%d').date()
                inv_qs = inv_qs.filter(creation_date__date__gte=date_from, creation_date__date__lte=date_to)
                quot_qs = quot_qs.filter(creation_date__date__gte=date_from, creation_date__date__lte=date_to)
                cust_qs = cust_qs.filter(registration_date__gte=date_from, registration_date__lte=date_to)
                
                last_day = calendar.monthrange(date_from.year, date_from.month)[1]
                if date_from.day == 1 and date_to.month == date_from.month and date_to.year == date_from.year and date_to.day == last_day:
                    target_year = date_from.year
                    target_month = date_from.month
                    if target_year == timezone.now().year and target_month == timezone.now().month:
                        is_current_month = True
                else:
                    using_custom_dates = True
                    target_year = date_from.year
                    target_month = date_from.month
            except ValueError:
                pass
        else:
            inv_qs = inv_qs.filter(creation_date__year=target_year, creation_date__month=target_month)
            quot_qs = quot_qs.filter(creation_date__year=target_year, creation_date__month=target_month)
            cust_qs = cust_qs.filter(registration_date__year=target_year, registration_date__month=target_month)
            if target_year == timezone.now().year and target_month == timezone.now().month:
                is_current_month = True

        # Invoices metrics
        total_invoices = inv_qs.count()
        revenue_ex_vat = inv_qs.annotate(inv_ex_vat=F('total_amount') - F('tax_amount')).aggregate(Sum('inv_ex_vat'))['inv_ex_vat__sum'] or Decimal('0.00')
        from sales.models import CreditNoteItem
        cn_items = CreditNoteItem.objects.filter(credit_note__original_invoice__in=inv_qs)
        credit_subtotal = cn_items.aggregate(Sum('credit_amount'))['credit_amount__sum'] or Decimal('0.00')
        total_sales_val = float(revenue_ex_vat - Decimal(str(credit_subtotal)))

        # Target metrics
        target_val = 0.0
        has_target = False
        if not using_custom_dates:
            sp_target = SalespersonTarget.objects.filter(salesperson=salesperson, year=target_year, month=target_month).first()
            if sp_target:
                target_val = float(sp_target.target_value)
                has_target = True

        # Quotation metrics
        total_quotations = quot_qs.count()
        won_quotations = quot_qs.filter(status=Quotation.Status.CONVERTED).count()
        lost_quotations = quot_qs.filter(status=Quotation.Status.CANCELLED).count()

        # Predictions (Run-rate for current month)
        prediction_val = 0.0
        if is_current_month and total_sales_val > 0:
            today = timezone.now().date()
            days_passed = today.day
            total_days = calendar.monthrange(today.year, today.month)[1]
            if days_passed > 0:
                daily_avg = total_sales_val / days_passed
                prediction_val = daily_avg * total_days

        # Category Breakdown
        cat_breakdown = []
        items = InvoiceItem.objects.filter(invoice__in=inv_qs).values('product__category').annotate(
            qty_sum=Sum('quantity')
        ).order_by('-qty_sum')
        for item in items:
            cat = item['product__category']
            cat_display = dict(Product.CategoryChoices.choices).get(cat, cat)
            cat_breakdown.append({
                'category': cat_display,
                'qty': int(item['qty_sum'])
            })

        # Sales Trend (Daily for specific month, or monthly for all time)
        trend_labels = []
        trend_sales = []
        
        if using_custom_dates and request.GET.get('all_time') == 'true':
            # Group by month
            from django.db.models.functions import TruncMonth
            monthly_sales = inv_qs.annotate(month=TruncMonth('creation_date')).values('month').annotate(
                total=Sum(F('total_amount') - F('tax_amount'))
            ).order_by('month')
            
            for ms in monthly_sales:
                if ms['month']:
                    trend_labels.append(ms['month'].strftime('%b %Y'))
                    trend_sales.append(float(ms['total']))
        else:
            # Group by day
            from django.db.models.functions import TruncDay
            daily_sales = inv_qs.annotate(day=TruncDay('creation_date')).values('day').annotate(
                total=Sum(F('total_amount') - F('tax_amount'))
            ).order_by('day')
            
            for ds in daily_sales:
                if ds['day']:
                    trend_labels.append(ds['day'].strftime('%d %b'))
                    trend_sales.append(float(ds['total']))

        return JsonResponse({
            'overview': {
                'sales': total_sales_val,
                'invoices': total_invoices,
                'new_customers': cust_qs.count(),
                'prediction': prediction_val,
            },
            'targets': {
                'has_target': has_target,
                'target': target_val,
            },
            'quotations': {
                'total': total_quotations,
                'won': won_quotations,
                'lost': lost_quotations,
            },
            'category_breakdown': cat_breakdown,
            'trends': {
                'labels': trend_labels,
                'sales': trend_sales,
            }
        })

