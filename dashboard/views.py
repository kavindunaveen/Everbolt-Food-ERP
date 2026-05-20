from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, F, Q
from django.utils import timezone
from collections import defaultdict

from sales.models import Invoice, InvoiceItem
from crm.models import Customer
from inventory.models import Product
from .models import SalesTarget


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

class DashboardDataAPI(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        year = request.GET.get('year', timezone.now().year)
        try:
            year = int(year)
        except:
            year = timezone.now().year

        # Base Query for the year (for issued/paid invoices)
        invoices = Invoice.objects.filter(
            creation_date__year=year,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        )
        invoice_items = InvoiceItem.objects.filter(invoice__in=invoices)

        # Overview Metrics
        total_invoices = invoices.count()
        total_customers = Customer.objects.count()
        
        # Consider Product.stock_unit == 'PACK' for total packs
        total_packs = invoice_items.filter(product__stock_unit='pack').aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        # Confectioneries Categories
        confectionery_sales = invoice_items.filter(product__category__icontains='Confectionery').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0
        overall_sales_total = invoice_items.annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        # Category Specific
        sugar_qty = invoice_items.filter(product__category__icontains='Sugar').aggregate(Sum('quantity'))['quantity__sum'] or 0
        sugar_sales = invoice_items.filter(product__category__icontains='Sugar').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        creamer_qty = invoice_items.filter(product__category__icontains='Creamer').aggregate(Sum('quantity'))['quantity__sum'] or 0
        creamer_sales = invoice_items.filter(product__category__icontains='Creamer').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        tea_qty = invoice_items.filter(product__category__icontains='Tea').aggregate(Sum('quantity'))['quantity__sum'] or 0
        tea_sales = invoice_items.filter(product__category__icontains='Tea').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        # Monthly Trends
        months_names = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
        
        trend_data = {
            'months': months_names,
            'sugar_sales': [0] * 12,
            'sugar_qty': [0] * 12,
            'creamer_sales': [0] * 12,
            'creamer_qty': [0] * 12,
            'tea_sales': [0] * 12,
            'tea_qty': [0] * 12,
            'overall_sales': [0] * 12,
        }

        monthly_items = invoice_items.values('invoice__creation_date__month', 'product__category').annotate(
            ex_vat_sales=F('line_total') - F('tax_amount')
        ).values('invoice__creation_date__month', 'product__category').annotate(
            t_sales=Sum('ex_vat_sales'),
            t_qty=Sum('quantity')
        )

        for item in monthly_items:
            m_idx = item['invoice__creation_date__month'] - 1  # 0-indexed
            c_name = (item['product__category'] or '').lower()
            val_sales = float(item['t_sales'] or 0)
            val_qty = float(item['t_qty'] or 0)

            trend_data['overall_sales'][m_idx] += val_sales

            if 'sugar' in c_name:
                trend_data['sugar_sales'][m_idx] += val_sales
                trend_data['sugar_qty'][m_idx] += val_qty
            elif 'creamer' in c_name:
                trend_data['creamer_sales'][m_idx] += val_sales
                trend_data['creamer_qty'][m_idx] += val_qty
            elif 'tea' in c_name:
                trend_data['tea_sales'][m_idx] += val_sales
                trend_data['tea_qty'][m_idx] += val_qty

        # Targets
        targets = SalesTarget.objects.filter(year=year).values('target_type', 'category', 'target_value')
        target_dict = {
            "overall": 0,
            "sugar": 0,
            "creamer": 0,
            "tea": 0
        }
        for t in targets:
            val = float(t['target_value'])
            if t['target_type'] == 'OVERALL_SALES':
                target_dict['overall'] += val
            elif t['target_type'] == 'CATEGORY_SALES':
                cat = (t['category'] or '').lower()
                if 'sugar' in cat: target_dict['sugar'] += val
                if 'creamer' in cat: target_dict['creamer'] += val
                if 'tea' in cat: target_dict['tea'] += val

        data = {
            "overview": {
                "total_invoices": total_invoices,
                "total_customers": total_customers,
                "total_packs": float(total_packs),
                "confectionery_sales": float(confectionery_sales),
                "overall_sales_total": float(overall_sales_total),
                "sugar_qty": float(sugar_qty),
                "sugar_sales": float(sugar_sales),
                "creamer_qty": float(creamer_qty),
                "creamer_sales": float(creamer_sales),
                "tea_qty": float(tea_qty),
                "tea_sales": float(tea_sales),
            },
            "trends": trend_data,
            "targets": target_dict
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
        year = request.GET.get('year', timezone.now().year)
        try:
            year = int(year)
        except Exception:
            year = timezone.now().year

        # Only issued / paid invoices for the selected year
        invoices = Invoice.objects.filter(
            creation_date__year=year,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        )

        # Pull every invoice item that belongs to a Confectionery product.
        # We also bring customer_name, month, product name in one queryset.
        raw_items = (
            InvoiceItem.objects
            .filter(invoice__in=invoices, product__category__iexact='Confectionery')
            .annotate(ex_vat=F('line_total') - F('tax_amount'))
            .values(
                'product__name',
                'quantity',
                'ex_vat',
                'invoice__customer__customer_name',
                'invoice__creation_date__month',
            )
        )

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
            qty     = float(row['quantity'] or 0)
            exvat   = float(row['ex_vat']   or 0)
            cust    = row['invoice__customer__customer_name'] or 'Unknown'
            m_idx   = (row['invoice__creation_date__month'] or 1) - 1  # 0-based

            label = classify_product(pname)
            if label is None:
                label = 'Other'

            sub_sales[label]  += exvat
            sub_qty[label]    += qty
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
            'year': year,
            'sub_product_totals': sub_product_totals,
            'by_customer': by_customer,
            'by_month': by_month,
        })
