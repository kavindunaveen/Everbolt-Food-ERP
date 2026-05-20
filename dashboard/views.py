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
        except Exception:
            year = timezone.now().year

        # Optional month filter (1–12). None = full year.
        month_raw = request.GET.get('month')
        month = None
        try:
            m = int(month_raw)
            if 1 <= m <= 12:
                month = m
        except (TypeError, ValueError):
            pass

        # Base invoices query
        inv_qs = Invoice.objects.filter(
            creation_date__year=year,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        )
        if month:
            inv_qs = inv_qs.filter(creation_date__month=month)

        invoice_items = InvoiceItem.objects.filter(invoice__in=inv_qs)

        # Overview Metrics
        total_invoices = inv_qs.count()
        total_customers = Customer.objects.count()
        total_packs = invoice_items.filter(product__stock_unit='pack').aggregate(Sum('quantity'))['quantity__sum'] or 0

        overall_sales_total = invoice_items.annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0
        confectionery_sales = invoice_items.filter(product__category__icontains='Confectionery').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        sugar_qty   = invoice_items.filter(product__category__icontains='Sugar').aggregate(Sum('quantity'))['quantity__sum'] or 0
        sugar_sales = invoice_items.filter(product__category__icontains='Sugar').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        creamer_qty   = invoice_items.filter(product__category__icontains='Creamer').aggregate(Sum('quantity'))['quantity__sum'] or 0
        creamer_sales = invoice_items.filter(product__category__icontains='Creamer').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        tea_qty   = invoice_items.filter(product__category__icontains='Tea').aggregate(Sum('quantity'))['quantity__sum'] or 0
        tea_sales = invoice_items.filter(product__category__icontains='Tea').annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(Sum('ex_vat'))['ex_vat__sum'] or 0

        # Monthly Trends (always show full year trend regardless of month filter)
        all_items_year = InvoiceItem.objects.filter(
            invoice__creation_date__year=year,
            invoice__status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        )
        months_names = ["January", "February", "March", "April", "May", "June",
                        "July", "August", "September", "October", "November", "December"]
        trend_data = {
            'months': months_names,
            'sugar_sales': [0] * 12, 'sugar_qty': [0] * 12,
            'creamer_sales': [0] * 12, 'creamer_qty': [0] * 12,
            'tea_sales': [0] * 12, 'tea_qty': [0] * 12,
            'overall_sales': [0] * 12,
        }
        monthly_items = all_items_year.values(
            'invoice__creation_date__month', 'product__category'
        ).annotate(
            ex_vat_sales=F('line_total') - F('tax_amount')
        ).values(
            'invoice__creation_date__month', 'product__category'
        ).annotate(t_sales=Sum('ex_vat_sales'), t_qty=Sum('quantity'))

        for item in monthly_items:
            m_idx  = item['invoice__creation_date__month'] - 1
            c_name = (item['product__category'] or '').lower()
            val_s  = float(item['t_sales'] or 0)
            val_q  = float(item['t_qty']   or 0)
            trend_data['overall_sales'][m_idx] += val_s
            if 'sugar' in c_name:
                trend_data['sugar_sales'][m_idx] += val_s
                trend_data['sugar_qty'][m_idx]   += val_q
            elif 'creamer' in c_name:
                trend_data['creamer_sales'][m_idx] += val_s
                trend_data['creamer_qty'][m_idx]   += val_q
            elif 'tea' in c_name:
                trend_data['tea_sales'][m_idx] += val_s
                trend_data['tea_qty'][m_idx]   += val_q

        # -------------------------------------------------------------------
        # Targets — month-aware
        # When a month is selected: look for a monthly target (month=month).
        # If none exists, return 0 (shown as "No Target" in gauges).
        # When full-year: look for yearly targets (month=None).
        # -------------------------------------------------------------------
        def _get_targets(for_month):
            qs = SalesTarget.objects.filter(year=year, month=for_month)
            d = {"overall": 0, "sugar": 0, "creamer": 0, "tea": 0, "has_target": False}
            for t in qs.values('target_type', 'category', 'target_value'):
                val = float(t['target_value'])
                if t['target_type'] == 'OVERALL_SALES':
                    d['overall'] += val
                    d['has_target'] = True
                elif t['target_type'] == 'CATEGORY_SALES':
                    cat = (t['category'] or '').lower()
                    if 'sugar'   in cat: d['sugar']   += val; d['has_target'] = True
                    if 'creamer' in cat: d['creamer'] += val; d['has_target'] = True
                    if 'tea'     in cat: d['tea']     += val; d['has_target'] = True
            return d

        target_dict = _get_targets(for_month=month)  # month is None = yearly

        data = {
            "month": month,
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


# ---------------------------------------------------------------------------
# Target Management View
# Access: user.is_admin() OR user.can_set_targets
# ---------------------------------------------------------------------------
import calendar as _calendar
from django.contrib import messages
from django.shortcuts import redirect

class TargetManagementView(LoginRequiredMixin, View):
    template_name = 'dashboard/targets.html'

    # Rows shown in the grid
    TARGET_ROWS = [
        {'label': 'Overall Sales',   'type': 'OVERALL_SALES',  'category': None,      'key': 'overall'},
        {'label': 'Sugar Sales',     'type': 'CATEGORY_SALES', 'category': 'Sugar',   'key': 'sugar'},
        {'label': 'Creamer Sales',   'type': 'CATEGORY_SALES', 'category': 'Creamer', 'key': 'creamer'},
        {'label': 'Tea Sales',       'type': 'CATEGORY_SALES', 'category': 'Tea',     'key': 'tea'},
    ]
    MONTH_NAMES = [_calendar.month_abbr[m] for m in range(1, 13)]

    def _check_access(self, request):
        return request.user.is_admin() or request.user.can_set_targets

    def get(self, request, *args, **kwargs):
        if not self._check_access(request):
            messages.error(request, "You don't have permission to manage targets.")
            return redirect('analytics_dashboard')

        year = request.GET.get('year', timezone.now().year)
        try:
            year = int(year)
        except Exception:
            year = timezone.now().year

        # Load all targets for this year into a lookup dict
        # key: (target_type, category_or_None, month_or_None) -> value
        existing = {}
        for t in SalesTarget.objects.filter(year=year):
            existing[(t.target_type, t.category, t.month)] = float(t.target_value)

        # Build grid data for template
        rows = []
        for row in self.TARGET_ROWS:
            periods = []
            # Yearly (month=None)
            yearly_key = (row['type'], row['category'], None)
            periods.append({
                'field_name': f"target_{row['key']}_yearly",
                'value': existing.get(yearly_key, ''),
                'label': 'Yearly',
            })
            # Monthly (1–12)
            for m in range(1, 13):
                monthly_key = (row['type'], row['category'], m)
                periods.append({
                    'field_name': f"target_{row['key']}_m{m}",
                    'value': existing.get(monthly_key, ''),
                    'label': self.MONTH_NAMES[m - 1],
                })
            rows.append({'label': row['label'], 'key': row['key'], 'periods': periods})

        available_years = list(range(timezone.now().year + 1, 2022, -1))

        return render(request, self.template_name, {
            'rows': rows,
            'year': year,
            'month_names': self.MONTH_NAMES,
            'available_years': available_years,
        })

    def post(self, request, *args, **kwargs):
        if not self._check_access(request):
            messages.error(request, "You don't have permission to manage targets.")
            return redirect('analytics_dashboard')

        year = request.POST.get('year')
        try:
            year = int(year)
        except Exception:
            messages.error(request, "Invalid year.")
            return redirect('target_management')

        saved = 0
        for row in self.TARGET_ROWS:
            # Yearly
            val_str = request.POST.get(f"target_{row['key']}_yearly", '').strip()
            self._upsert(year, row['type'], row['category'], None, val_str)
            if val_str:
                saved += 1
            # Monthly
            for m in range(1, 13):
                val_str = request.POST.get(f"target_{row['key']}_m{m}", '').strip()
                self._upsert(year, row['type'], row['category'], m, val_str)
                if val_str:
                    saved += 1

        messages.success(request, f"Targets for {year} saved successfully ({saved} entries updated).")
        return redirect(f"{request.path}?year={year}")

    @staticmethod
    def _upsert(year, target_type, category, month, val_str):
        """Create or update a target; delete if value is cleared."""
        if val_str:
            try:
                val = float(val_str)
                SalesTarget.objects.update_or_create(
                    year=year, month=month, target_type=target_type, category=category,
                    defaults={'target_value': val}
                )
            except ValueError:
                pass
        else:
            # Empty string = clear the target
            SalesTarget.objects.filter(
                year=year, month=month, target_type=target_type, category=category
            ).delete()
