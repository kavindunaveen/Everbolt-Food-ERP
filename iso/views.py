from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.db import transaction

from users.mixins import ERPPermissionRequiredMixin
from users.models import Notification
from .models import ISOCriteria, ISODailyPlan, ISODailyTask, User
from .forms import ISOCriteriaForm, ISODailyPlanForm

class CriteriaListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = ISOCriteria
    template_name = 'iso/criteria_list.html'
    context_object_name = 'criteria_list'
    permission_required = 'iso.view_isocriteria'

    def get_queryset(self):
        return ISOCriteria.objects.select_related('category', 'created_by').order_by('-created_at')

class CriteriaCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    model = ISOCriteria
    form_class = ISOCriteriaForm
    template_name = 'iso/criteria_form.html'
    permission_required = 'iso.add_isocriteria'
    success_url = reverse_lazy('iso_criteria_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        return data

    def form_valid(self, form):
        with transaction.atomic():
            form.instance.created_by = self.request.user
            self.object = form.save()
                
        messages.success(self.request, "ISO Criteria created successfully.")
        return super().form_valid(form)

class CriteriaUpdateView(LoginRequiredMixin, ERPPermissionRequiredMixin, UpdateView):
    model = ISOCriteria
    form_class = ISOCriteriaForm
    template_name = 'iso/criteria_form.html'
    success_url = reverse_lazy('iso_criteria_list')
    permission_required = 'iso.change_isocriteria'

    def form_valid(self, form):
        messages.success(self.request, "ISO Criteria updated successfully.")
        return super().form_valid(form)

class CriteriaDeleteView(LoginRequiredMixin, ERPPermissionRequiredMixin, DeleteView):
    model = ISOCriteria
    template_name = 'iso/criteria_confirm_delete.html'
    success_url = reverse_lazy('iso_criteria_list')
    permission_required = 'iso.delete_isocriteria'

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "ISO Criteria deleted successfully.")
        return super().delete(request, *args, **kwargs)

class DailyPlanListView(LoginRequiredMixin, ERPPermissionRequiredMixin, ListView):
    model = ISODailyPlan
    template_name = 'iso/daily_plan_list.html'
    context_object_name = 'plans'
    permission_required = 'iso.view_isodailyplan'

    def get_queryset(self):
        criteria_id = self.kwargs.get('criteria_id')
        self.criteria = get_object_or_404(ISOCriteria, pk=criteria_id)
        return ISODailyPlan.objects.filter(criteria=self.criteria).select_related('submitted_by').prefetch_related('tasks').order_by('-date', '-submitted_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['criteria'] = self.criteria
        return context

class DailyPlanCreateView(LoginRequiredMixin, ERPPermissionRequiredMixin, CreateView):
    model = ISODailyPlan
    form_class = ISODailyPlanForm
    template_name = 'iso/daily_plan_form.html'
    permission_required = 'iso.add_isodailyplan'

    def dispatch(self, request, *args, **kwargs):
        self.criteria = get_object_or_404(ISOCriteria, pk=kwargs.get('criteria_id'))
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['criteria'] = self.criteria
        return context

    def form_valid(self, form):
        # We need to process the submitted task data from the frontend manually
        
        # Check if plan for this date and criteria already exists
        date = form.cleaned_data['date']
        if ISODailyPlan.objects.filter(criteria=self.criteria, date=date).exists():
            messages.error(self.request, f"A checklist for {date} already exists for this criteria.")
            return self.form_invalid(form)

        with transaction.atomic():
            plan = form.save(commit=False)
            plan.criteria = self.criteria
            plan.submitted_by = self.request.user
            plan.save()

            # The frontend will send lists of arrays like:
            # task_descriptions[], is_checked[], remarks[]
            task_descriptions = self.request.POST.getlist('task_descriptions[]')
            remarks = self.request.POST.getlist('remarks[]')
            
            tasks_to_create = []
            for i, desc in enumerate(task_descriptions):
                if not desc.strip():
                    continue
                is_checked_str = self.request.POST.get(f'is_checked_{i}', 'false')
                is_checked = (is_checked_str == 'true')
                
                tasks_to_create.append(ISODailyTask(
                    plan=plan,
                    task_description=desc,
                    is_checked=is_checked,
                    remark=remarks[i] if i < len(remarks) else ''
                ))
            
            if tasks_to_create:
                ISODailyTask.objects.bulk_create(tasks_to_create)
            
            # Trigger Admin Notifications
            admins = User.objects.filter(role=User.Role.ADMIN, is_active=True)
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    title=f"ISO Checklist Submitted: {self.criteria.name}",
                    message=f"{self.request.user.get_full_name()} submitted the daily ISO Checklist for {date}.",
                    notification_type='system_alert',
                    related_url=reverse('iso_plan_list', args=[self.criteria.id])
                )

        messages.success(self.request, "Daily ISO Checklist submitted successfully.")
        return redirect('iso_plan_list', criteria_id=self.criteria.id)

class DailyPlanDetailView(LoginRequiredMixin, ERPPermissionRequiredMixin, DetailView):
    model = ISODailyPlan
    template_name = 'iso/daily_plan_detail.html'
    context_object_name = 'plan'
    permission_required = 'iso.view_isodailyplan'
    pk_url_kwarg = 'plan_id'
