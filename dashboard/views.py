from django.shortcuts import render
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Sum, Count, F
from django.utils import timezone

from sales.models import Invoice, InvoiceItem
from crm.models import Customer
from inventory.models import Category, Product
from .models import SalesTarget

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
        total_packs = invoice_items.filter(product__stock_unit='PACK').aggregate(Sum('quantity'))['quantity__sum'] or 0
        
        # Confectioneries Categories
        confectionery_sales = invoice_items.filter(product__category__name__icontains='CONFECTIONARIES').aggregate(Sum('line_total'))['line_total__sum'] or 0
        overall_sales_total = invoice_items.aggregate(Sum('line_total'))['line_total__sum'] or 0

        # Category Specific
        sugar_qty = invoice_items.filter(product__category__name__icontains='Sugar').aggregate(Sum('quantity'))['quantity__sum'] or 0
        sugar_sales = invoice_items.filter(product__category__name__icontains='Sugar').aggregate(Sum('line_total'))['line_total__sum'] or 0

        creamer_qty = invoice_items.filter(product__category__name__icontains='Creamer').aggregate(Sum('quantity'))['quantity__sum'] or 0
        creamer_sales = invoice_items.filter(product__category__name__icontains='Creamer').aggregate(Sum('line_total'))['line_total__sum'] or 0

        tea_qty = invoice_items.filter(product__category__name__icontains='Tea').aggregate(Sum('quantity'))['quantity__sum'] or 0
        tea_sales = invoice_items.filter(product__category__name__icontains='Tea').aggregate(Sum('line_total'))['line_total__sum'] or 0

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

        monthly_items = invoice_items.values('invoice__creation_date__month', 'product__category__name').annotate(
            t_sales=Sum('line_total'),
            t_qty=Sum('quantity')
        )

        for item in monthly_items:
            m_idx = item['invoice__creation_date__month'] - 1  # 0-indexed
            c_name = (item['product__category__name'] or '').lower()
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
        targets = SalesTarget.objects.filter(year=year).values('target_type', 'category__name', 'target_value')
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
                cat = (t['category__name'] or '').lower()
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
