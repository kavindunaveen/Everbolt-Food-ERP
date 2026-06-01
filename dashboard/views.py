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
        total_customers = inv_qs.values('customer').distinct().count()
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
            sugar_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='sugar') | Q(target_group__products__name__icontains='sugar') | Q(target_group__name__icontains='sugar'),
                year=year, month=for_month
            ).distinct()
            sugar_t = sum(float(pt.target_value) for pt in sugar_qs)

            creamer_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='creamer') | Q(target_group__products__name__icontains='creamer') | Q(target_group__name__icontains='creamer'),
                year=year, month=for_month
            ).distinct()
            creamer_t = sum(float(pt.target_value) for pt in creamer_qs)

            tea_qs = ProductTarget.objects.filter(
                Q(target_group__products__category__icontains='tea') | Q(target_group__name__icontains='tea'),
                year=year, month=for_month
            ).exclude(
                Q(target_group__products__name__icontains='catering tea') | Q(target_group__name__icontains='catering tea')
            ).distinct()
            tea_t = sum(float(pt.target_value) for pt in tea_qs)

            overall_qs = ProductTarget.objects.filter(
                year=year, month=for_month
            ).distinct()
            overall_t = get_target_value_rs(overall_qs)

            has_target = ProductTarget.objects.filter(year=year, month=for_month).exists()

            return {
                "overall": overall_t,
                "sugar": sugar_t,
                "creamer": creamer_t,
                "tea": tea_t,
                "has_target": has_target
            }

        target_dict = _get_targets(for_month=month)  # month is None = yearly

        # ── Target achievement list by product category ──────────────────
        def _get_pct(achieved, target):
            return round((achieved / target) * 100, 2) if target > 0 else 0.0

        achievement_rows = []
        for group in ProductTargetGroup.objects.all().prefetch_related('products'):
            products = list(group.products.all())
            if not products:
                sales = 0.0
                achieved_qty = 0.0
            else:
                items_group = invoice_items.filter(product__in=products)
                sales = float(items_group.annotate(ex_vat=F('line_total') - F('tax_amount')).aggregate(s=Sum('ex_vat'))['s'] or 0)
                achieved_qty = float(items_group.aggregate(s=Sum('quantity'))['s'] or 0)
            
            group_targets = ProductTarget.objects.filter(target_group=group, year=year, month=month)
            target_qty = float(group_targets.aggregate(s=Sum('target_value'))['s'] or 0)
            
            achievement_rows.append({
                'category': group.name,
                'sales': sales,
                'achieved_qty': achieved_qty,
                'target': target_qty,
                'pct': _get_pct(achieved_qty, target_qty),
                'has_target': target_qty > 0
            })

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
        year = request.GET.get('year', timezone.now().year)
        try:
            year = int(year)
        except Exception:
            year = timezone.now().year

        month_raw = request.GET.get('month')
        month = None
        try:
            m = int(month_raw)
            if 1 <= m <= 12:
                month = m
        except (TypeError, ValueError):
            pass

        # Only issued / paid invoices for the selected year/month
        inv_qs = Invoice.objects.filter(
            creation_date__year=year,
            status__in=[Invoice.Status.ISSUED, Invoice.Status.PAID]
        )
        if month:
            inv_qs = inv_qs.filter(creation_date__month=month)

        invoices = inv_qs

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
        for sp in User.objects.filter(role=User.Roles.SALES_OFFICER).order_by('username'):
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

        # ── action == 'save_targets' ────────────────────────────────────
        for group in ProductTargetGroup.objects.all():
            for m in range(1, 13):
                _upsert_group_target(group, year, m, request.POST.get(f"gt_{group.id}_m{m}"))

        for sp in User.objects.filter(role=User.Roles.SALES_OFFICER):
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
        if len(q) < 2:
            return JsonResponse({'results': []})

        # Exclude products already linked to a target group
        linked_pids = set(ProductTargetGroup.objects.values_list('products__id', flat=True))

        products = (
            Product.objects
            .filter(
                Q(name__icontains=q) | Q(product_id__icontains=q),
                status=True,
            )
            .exclude(id__in=linked_pids)
            .order_by('name')[:25]
        )

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
        year = int(request.GET.get('year', timezone.now().year))
        month_raw = request.GET.get('month')
        month = None
        try:
            m = int(month_raw)
            if 1 <= m <= 12:
                month = m
        except (TypeError, ValueError):
            pass

        STATUSES = [Invoice.Status.ISSUED, Invoice.Status.PAID]
        results = []

        for group in ProductTargetGroup.objects.prefetch_related('products').all():
            products_list = list(group.products.all())
            if not products_list:
                continue

            # ── Actual sales for selected period ─────────────────────────
            items_qs = InvoiceItem.objects.filter(
                product__in=products_list,
                invoice__creation_date__year=year,
                invoice__status__in=STATUSES,
            )
            if month:
                items_qs = items_qs.filter(invoice__creation_date__month=month)

            actual = float(
                items_qs.annotate(ex_vat=F('line_total') - F('tax_amount'))
                .aggregate(s=Sum('ex_vat'))['s'] or 0
            )
            actual_qty = float(
                items_qs.aggregate(q=Sum('quantity'))['q'] or 0
            )

            # ── Target for this period ────────────────────────────────────
            try:
                pt = ProductTarget.objects.get(target_group=group, year=year, month=month)
                target_qty = float(pt.target_value)
                has_target = True
            except ProductTarget.DoesNotExist:
                target_qty = 0.0
                has_target = False

            pct = round(actual_qty / target_qty * 100, 1) if target_qty > 0 else 0

            # ── Monthly trend (always full 12 months) ─────────────────────
            all_year_qs = InvoiceItem.objects.filter(
                product__in=products_list,
                invoice__creation_date__year=year,
                invoice__status__in=STATUSES,
            ).annotate(ex_vat=F('line_total') - F('tax_amount')).values(
                'invoice__creation_date__month'
            ).annotate(s=Sum('ex_vat'))

            monthly_trend = [0.0] * 12
            for row in all_year_qs:
                monthly_trend[row['invoice__creation_date__month'] - 1] = round(
                    float(row['s'] or 0), 2)

            # ── Monthly targets ───────────────────────────────────────────
            monthly_targets = [0.0] * 12
            for pt_m in ProductTarget.objects.filter(target_group=group, year=year,
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

        return JsonResponse({'year': year, 'month': month, 'products': results})
