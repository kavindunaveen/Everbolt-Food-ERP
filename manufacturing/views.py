from users.mixins import ERPPermissionRequiredMixin
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.conf import settings

from .models import BOM, BOMItem, Production
from inventory.models import Product
from .forms import (
    BOMForm, BOMItemFormSet, 
    ProductionForm, ProductionMaterialFormSet, ProductionOutputFormSet
)
from .services import confirm_production, cancel_production

# --- Dashboard ---
class ManufacturingDashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'manufacturing/dashboard.html'

# --- BOM Views ---

class BOMListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    permission_required = 'manufacturing.view_bom'
    model = BOM
    template_name = 'manufacturing/bom_list.html'
    context_object_name = 'boms'
    paginate_by = 20
    ordering = ['-id']

class BOMCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    permission_required = 'manufacturing.add_bom'
    model = BOM
    form_class = BOMForm
    template_name = 'manufacturing/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = BOMItemFormSet(self.request.POST)
        else:
            data['items'] = BOMItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
        return super().form_valid(form)

class BOMDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    permission_required = 'manufacturing.view_bom'
    model = BOM
    template_name = 'manufacturing/bom_detail.html'
    context_object_name = 'bom'

class BOMUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
    permission_required = 'manufacturing.change_bom'
    model = BOM
    form_class = BOMForm
    template_name = 'manufacturing/bom_form.html'
    success_url = reverse_lazy('bom_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = BOMItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = BOMItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        with transaction.atomic():
            self.object = form.save()
            if items.is_valid():
                items.instance = self.object
                items.save()
        return super().form_valid(form)

# --- Production Views ---

class ProductionListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    permission_required = 'manufacturing.view_production'
    model = Production
    template_name = 'manufacturing/production_list.html'
    context_object_name = 'productions'
    paginate_by = 20
    ordering = ['-id']

class ProductionCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    permission_required = 'manufacturing.add_production'
    model = Production
    form_class = ProductionForm
    template_name = 'manufacturing/production_form.html'
    success_url = reverse_lazy('production_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['materials'] = ProductionMaterialFormSet(self.request.POST, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(self.request.POST, prefix='outputs')
        else:
            data['materials'] = ProductionMaterialFormSet(prefix='materials')
            data['outputs'] = ProductionOutputFormSet(prefix='outputs')
        data['all_products'] = Product.objects.filter(status=True)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        materials = context['materials']
        outputs = context['outputs']
        
        if not (materials.is_valid() and outputs.is_valid()):
            return self.form_invalid(form)
            
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
            materials.instance = self.object
            materials.save()
            outputs.instance = self.object
            outputs.save()
                
        messages.success(self.request, "Production order created as Draft.")
        return super().form_valid(form)

class ProductionUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
    permission_required = 'manufacturing.change_production'
    model = Production
    form_class = ProductionForm
    template_name = 'manufacturing/production_form.html'
    success_url = reverse_lazy('production_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['materials'] = ProductionMaterialFormSet(self.request.POST, instance=self.object, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(self.request.POST, instance=self.object, prefix='outputs')
        else:
            data['materials'] = ProductionMaterialFormSet(instance=self.object, prefix='materials')
            data['outputs'] = ProductionOutputFormSet(instance=self.object, prefix='outputs')
        data['all_products'] = Product.objects.filter(status=True)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        materials = context['materials']
        outputs = context['outputs']
        
        if not (materials.is_valid() and outputs.is_valid()):
            return self.form_invalid(form)
            
        with transaction.atomic():
            self.object = form.save()
            materials.instance = self.object
            materials.save()
            outputs.instance = self.object
            outputs.save()
            
        return super().form_valid(form)

class ProductionDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    permission_required = 'manufacturing.view_production'
    model = Production
    template_name = 'manufacturing/production_detail.html'
    context_object_name = 'production'

@login_required
def confirm_production_view(request, pk):
    production = get_object_or_404(Production, pk=pk)
    if request.method == 'POST':
        try:
            confirm_production(production, request.user)
            messages.success(request, f"Production {production.production_number} confirmed. Stock adjusted.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('production_detail', pk=pk)

@login_required
def cancel_production_view(request, pk):
    production = get_object_or_404(Production, pk=pk)
    if request.method == 'POST':
        try:
            cancel_production(production, request.user)
            messages.success(request, f"Production {production.production_number} cancelled. Stock reversed.")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")
    return redirect('production_detail', pk=pk)

# AJAX API to get BOM details
def get_bom_details(request, bom_id):
    bom = get_object_or_404(BOM, pk=bom_id)
    items = []
    for item in bom.items.all():
        items.append({
            'product_id': item.component_product.id,
            'product_name': item.component_product.name,
            'qty': str(item.qty_required)
        })
    return JsonResponse({
        'finished_product_id': bom.finished_product.id,
        'finished_product_name': bom.finished_product.name,
        'items': items
    })

import json
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.auth import get_user_model
from django.views.generic import TemplateView
from .models import DailyProductionPlan, ProductionPlanLine

class ProductionPlanListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    permission_required = 'manufacturing.manage_production_plans'
    model = DailyProductionPlan
    template_name = 'manufacturing/production_plan_list.html'
    context_object_name = 'plans'
    ordering = ['-date']

class ProductionPlanDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    permission_required = 'manufacturing.manage_production_plans'
    model = DailyProductionPlan
    template_name = 'manufacturing/production_plan_detail.html'
    context_object_name = 'plan'

class ProductionPlanCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, TemplateView):
    permission_required = 'manufacturing.manage_production_plans'
    template_name = 'manufacturing/production_plan_form.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_products = Product.objects.filter(status=True, inventory_class='FINISHED').values('id', 'name', 'product_id')
        raw_materials = Product.objects.filter(status=True, inventory_class='RAW').values('id', 'name', 'product_id')
        
        context['all_products_json'] = json.dumps(list(all_products))
        context['raw_materials_json'] = json.dumps(list(raw_materials))
        
        context['plan_data_json'] = json.dumps({
            'date': timezone.now().date().strftime('%Y-%m-%d'),
            'status': 'DRAFT',
            'lines': [{
                'target_product_id': '',
                'unit_weight': 0,
                'target_qty': 0,
                'raw_material_id': '',
                'raw_material_qty': 0,
                'actual_used_qty': 0,
                'wastage_qty': 0,
                'rm_wastage_unit': 'g',
                'pm_wastage_qty': 0,
                'pm_wastage_unit': 'g',
                'wastage_remark': '',
                'actual_completed_qty': 0,
                'note': ''
            }]
        })
        return context

class ProductionPlanUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    permission_required = 'manufacturing.manage_production_plans'
    model = DailyProductionPlan
    template_name = 'manufacturing/production_plan_form.html'
    context_object_name = 'plan'

    def dispatch(self, request, *args, **kwargs):
        obj = self.get_object()
        if request.user != obj.created_by and request.user != obj.submitted_by and not request.user.is_superuser:
            messages.error(request, "You do not have permission to edit this plan. Only the creator or submitter can edit it.")
            return redirect('production_plan_detail', pk=obj.pk)
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        all_products = Product.objects.filter(status=True, inventory_class='FINISHED').values('id', 'name', 'product_id')
        raw_materials = Product.objects.filter(status=True, inventory_class='RAW').values('id', 'name', 'product_id')
        
        context['all_products_json'] = json.dumps(list(all_products))
        context['raw_materials_json'] = json.dumps(list(raw_materials))
        
        plan = self.object
        lines = []
        for l in plan.lines.all():
            lines.append({
                'target_product_id': str(l.target_product_id) if l.target_product_id else '',
                'unit_weight': float(l.unit_weight),
                'target_qty': l.target_qty,
                'raw_material_id': str(l.raw_material_id) if l.raw_material_id else '',
                'raw_material_qty': float(l.raw_material_qty),
                'actual_used_qty': float(l.actual_used_qty),
                'wastage_qty': float(l.wastage_qty),
                'rm_wastage_unit': l.rm_wastage_unit,
                'pm_wastage_qty': float(l.pm_wastage_qty),
                'pm_wastage_unit': l.pm_wastage_unit,
                'wastage_remark': l.wastage_remark or '',
                'actual_completed_qty': l.actual_completed_qty,
                'note': l.note or ''
            })
            
        context['plan_data_json'] = json.dumps({
            'date': plan.date.strftime('%Y-%m-%d'),
            'status': plan.status,
            'lines': lines
        })
        return context

@login_required
def save_production_plan(request):
    if not request.user.has_perm('manufacturing.manage_production_plans'):
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'}, status=403)
        
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            date_str = data.get('date')
            action = data.get('action') # 'save_draft', 'submit_morning', 'submit_evening'
            lines = data.get('lines', [])
            
            if not date_str:
                return JsonResponse({'status': 'error', 'message': 'Date is required.'}, status=400)
                
            from datetime import datetime
            plan_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            with transaction.atomic():
                plan, created = DailyProductionPlan.objects.get_or_create(
                    date=plan_date,
                    defaults={'created_by': request.user}
                )
                
                if plan.status == 'COMPLETED' and action != 'update_evening':
                    return JsonResponse({'status': 'error', 'message': 'This plan is already completed.'}, status=400)
                
                plan.lines.all().delete()
                for line in lines:
                    target_prod = Product.objects.get(id=line['target_product_id'])
                    raw_mat = Product.objects.get(id=line['raw_material_id'])
                    target_qty = line.get('target_qty') or 0
                    actual_completed_qty = line.get('actual_completed_qty') or 0
                    note = line.get('note') or ''
                    
                    if (action in ['submit_evening', 'update_evening'] or plan.status == 'COMPLETED') and (int(actual_completed_qty) != int(target_qty)):
                        if not note.strip():
                            return JsonResponse({'status': 'error', 'message': f"A note is required for '{target_prod.name}' because the Actual Qty ({actual_completed_qty}) does not match Target Qty ({target_qty})."}, status=400)
                            
                    ProductionPlanLine.objects.create(
                        plan=plan,
                        target_product=target_prod,
                        unit_weight=line.get('unit_weight') or 0,
                        target_qty=target_qty,
                        raw_material=raw_mat,
                        raw_material_qty=line.get('raw_material_qty') or 0,
                        actual_used_qty=line.get('actual_used_qty') or 0,
                        wastage_qty=line.get('wastage_qty') or 0,
                        rm_wastage_unit=line.get('rm_wastage_unit') or 'g',
                        pm_wastage_qty=line.get('pm_wastage_qty') or 0,
                        pm_wastage_unit=line.get('pm_wastage_unit') or 'g',
                        wastage_remark=line.get('wastage_remark') or '',
                        actual_completed_qty=actual_completed_qty,
                        note=note
                    )
                    
                email_subject = None
                email_body = None

                if action == 'submit_morning':
                    if not request.user.has_perm('manufacturing.submit_production_plans'):
                        return JsonResponse({'status': 'error', 'message': 'You do not have permission to submit.'}, status=403)
                    plan.status = 'MORNING_SUBMITTED'
                    plan.save()
                    email_subject = f"Morning Production Plan Submitted: {plan.date}"
                    email_body = f"The morning production targets for {plan.date} have been set by {request.user.get_full_name() or request.user.username}.\n\nPlease log in to the ERP to view the details.\nhttps://erp.organicfoodslanka.com/manufacturing/planning/{plan.id}/edit/"
                    notif_link = reverse('production_plan_edit', args=[plan.id])

                elif action == 'submit_evening':
                    if not request.user.has_perm('manufacturing.submit_production_plans'):
                        return JsonResponse({'status': 'error', 'message': 'You do not have permission to submit.'}, status=403)
                    plan.status = 'COMPLETED'
                    plan.submitted_by = request.user
                    plan.submitted_at = timezone.now()
                    plan.save()
                    email_subject = f"End-of-Day Production Plan Completed: {plan.date}"
                    email_body = f"The end-of-day production actuals for {plan.date} have been submitted by {request.user.get_full_name() or request.user.username}.\n\nTotal Items Produced: {sum(l.actual_completed_qty for l in plan.lines.all())}\n\nPlease log in to the ERP to view the variance details.\nhttps://erp.organicfoodslanka.com/manufacturing/planning/{plan.id}/"
                    notif_link = reverse('production_plan_detail', args=[plan.id])
                    
                elif action == 'update_morning':
                    if not request.user.has_perm('manufacturing.submit_production_plans'):
                        return JsonResponse({'status': 'error', 'message': 'You do not have permission to update.'}, status=403)
                    email_subject = f"Morning Production Plan Updated: {plan.date}"
                    email_body = f"The morning production targets for {plan.date} have been updated by {request.user.get_full_name() or request.user.username}.\n\nPlease log in to the ERP to view the details.\nhttps://erp.organicfoodslanka.com/manufacturing/planning/{plan.id}/edit/"
                    notif_link = reverse('production_plan_edit', args=[plan.id])

                elif action == 'update_evening':
                    if not request.user.has_perm('manufacturing.submit_production_plans'):
                        return JsonResponse({'status': 'error', 'message': 'You do not have permission to update.'}, status=403)
                    email_subject = f"Completed Production Plan Updated: {plan.date}"
                    email_body = f"The completed production actuals for {plan.date} have been updated by {request.user.get_full_name() or request.user.username}.\n\nTotal Items Produced: {sum(l.actual_completed_qty for l in plan.lines.all())}\n\nPlease log in to the ERP to view the variance details.\nhttps://erp.organicfoodslanka.com/manufacturing/planning/{plan.id}/"
                    notif_link = reverse('production_plan_detail', args=[plan.id])

                if email_subject:
                    User = get_user_model()
                    from django.db.models import Q
                    all_users = User.objects.filter(
                        Q(user_permissions__codename='receive_production_notifications') |
                        Q(role__permissions__codename='receive_production_notifications') |
                        Q(is_superuser=True)
                    ).distinct()
                    from users.models import Notification
                    
                    emails_to_send = []
                    for u in all_users:
                        Notification.objects.create(
                            recipient=u,
                            title=email_subject,
                            message=email_body.split('\n')[0],
                            link=notif_link
                        )
                        if u.email and action not in ['update_morning', 'update_evening']:
                            emails_to_send.append(u.email)

                    if emails_to_send:
                        import threading
                        def send_alerts(subj, body, emails):
                            for email in emails:
                                send_mail(subj, body, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                        
                        thread = threading.Thread(target=send_alerts, args=(email_subject, email_body, emails_to_send))
                        thread.start()

            return JsonResponse({'status': 'ok', 'message': "Plan saved successfully.", 'id': plan.id})
            
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)
