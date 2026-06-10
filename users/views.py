from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from users.mixins import ERPPermissionRequiredMixin
from .models import User, Role
from .forms import CustomUserCreationForm, CustomUserChangeForm, RoleForm
from django.db.models import Q
from django.contrib import messages

from django.contrib.auth.mixins import UserPassesTestMixin
from users.mixins import ERPUserPassesTestMixin
class AdminRequiredMixin(ERPUserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_admin()

class UserListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        role_filter = self.request.GET.get('role')
        if q:
            qs = qs.filter(
                Q(username__icontains=q) | 
                Q(first_name__icontains=q) | 
                Q(last_name__icontains=q) | 
                Q(email__icontains=q)
            )
        if role_filter:
            qs = qs.filter(role__pk=role_filter)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['roles'] = Role.objects.all()
        context['total_users'] = User.objects.count()
        context['active_users'] = User.objects.filter(is_active=True).count()
        context['inactive_users'] = User.objects.filter(is_active=False).count()
        context['total_roles'] = Role.objects.count()
        return context

class UserCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

class UserUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

class UserDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')


# ==========================================
# Role Management Views
# ==========================================

class RoleListView(LoginRequiredMixin, AdminRequiredMixin, ListView):
    model = Role
    template_name = 'users/role_list.html'
    context_object_name = 'roles'
    paginate_by = 20

class RoleCreateView(LoginRequiredMixin, AdminRequiredMixin, CreateView):
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('role_list')

class RoleUpdateView(LoginRequiredMixin, AdminRequiredMixin, UpdateView):
    model = Role
    form_class = RoleForm
    template_name = 'users/role_form.html'
    success_url = reverse_lazy('role_list')

class RoleDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    model = Role
    template_name = 'users/role_confirm_delete.html'
    success_url = reverse_lazy('role_list')

    def post(self, request, *args, **kwargs):
        role = self.get_object()
        if role.is_system:
            messages.error(request, "Cannot delete system roles.")
            return redirect('role_list')
        if role.users.exists():
            messages.error(request, "Cannot delete role because it is assigned to users.")
            return redirect('role_list')
        return super().post(request, *args, **kwargs)

# ==========================================

from django import forms
class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'contact_number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].disabled = True
        self.fields['email'].help_text = "Only an administrator can change your email address."

class ProfileUpdateView(LoginRequiredMixin, UpdateView):
    model = User
    form_class = ProfileUpdateForm
    template_name = 'users/profile_form.html'
    success_url = reverse_lazy('sales_dashboard')

    def get_object(self):
        return self.request.user


from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required

@login_required
def notification_read(request, pk):
    from .models import Notification
    notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
    notification.is_read = True
    notification.save()
    if notification.link:
        return redirect(notification.link)
    
    referer = request.META.get('HTTP_REFERER')
    if referer:
        return redirect(referer)
    return redirect('sales_dashboard')

@login_required
def action_center(request):
    from .models import Notification
    from sales.models import Invoice
    
    # All notifications history
    notifications = Notification.objects.filter(recipient=request.user).order_by('-created_at')
    
    # Pending approvals assigned to this user
    pending_edits = Invoice.objects.filter(status='EDIT_PENDING', designated_approver=request.user)
    
    # Unassigned general approvals (only if user has perm)
    if request.user.has_perm('sales.approve_invoice'):
        pending_general = Invoice.objects.filter(status__in=['APPROVAL_PENDING', 'CANCEL_PENDING'])
    else:
        pending_general = Invoice.objects.none()
        
    return render(request, 'users/action_center.html', {
        'notifications': notifications,
        'pending_edits': pending_edits,
        'pending_general': pending_general,
    })

from django.views import View
from django.http import JsonResponse
from .models import SavedFilter
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
import json

@method_decorator(login_required, name='dispatch')
class SaveFilterView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            model_name = data.get('model_name')
            name = data.get('name')
            query_string = data.get('query_string')
            
            if not all([model_name, name, query_string]):
                return JsonResponse({'status': 'error', 'message': 'Missing fields'}, status=400)
                
            SavedFilter.objects.create(
                user=request.user,
                model_name=model_name,
                name=name,
                query_string=query_string
            )
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@method_decorator(login_required, name='dispatch')
class DeleteFilterView(View):
    def post(self, request, pk, *args, **kwargs):
        try:
            saved_filter = get_object_or_404(SavedFilter, pk=pk, user=request.user)
            saved_filter.delete()
            return JsonResponse({'status': 'success'})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
