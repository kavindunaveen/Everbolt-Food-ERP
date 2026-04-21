from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from .models import User
from .forms import CustomUserCreationForm, CustomUserChangeForm
from django.db.models import Q

class UserListView(LoginRequiredMixin, PermissionRequiredMixin, ListView):
    permission_required = 'users.view_user'
    model = User
    template_name = 'users/user_list.html'
    context_object_name = 'users'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(
                Q(username__icontains=q) | 
                Q(first_name__icontains=q) | 
                Q(last_name__icontains=q) | 
                Q(email__icontains=q)
            )
        return qs

class UserCreateView(LoginRequiredMixin, PermissionRequiredMixin, CreateView):
    permission_required = 'users.add_user'
    model = User
    form_class = CustomUserCreationForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

class UserUpdateView(LoginRequiredMixin, PermissionRequiredMixin, UpdateView):
    permission_required = 'users.change_user'
    model = User
    form_class = CustomUserChangeForm
    template_name = 'users/user_form.html'
    success_url = reverse_lazy('user_list')

class UserDeleteView(LoginRequiredMixin, PermissionRequiredMixin, DeleteView):
    permission_required = 'users.delete_user'
    model = User
    template_name = 'users/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')

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
    return redirect('sales_dashboard')

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
