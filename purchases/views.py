from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy, reverse
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from .models import GRN
from .forms import GRNForm, GRNItemFormSet
from .services import confirm_grn, cancel_grn

class GRNListView(LoginRequiredMixin, ListView):
    model = GRN
    template_name = 'purchases/grn_list.html'
    context_object_name = 'grns'
    ordering = ['-id']

class GRNDetailView(LoginRequiredMixin, DetailView):
    model = GRN
    template_name = 'purchases/grn_detail.html'
    context_object_name = 'grn'

class GRNCreateView(LoginRequiredMixin, CreateView):
    model = GRN
    form_class = GRNForm
    template_name = 'purchases/grn_form.html'
    success_url = reverse_lazy('grn_list')

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = GRNItemFormSet(self.request.POST)
        else:
            data['items'] = GRNItemFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            form.instance.created_by = self.request.user
            self.object = form.save()
            items.instance = self.object
            items.save()
            messages.success(self.request, f"GRN {self.object.grn_number} created successfully as Draft.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

class GRNUpdateView(LoginRequiredMixin, UpdateView):
    model = GRN
    form_class = GRNForm
    template_name = 'purchases/grn_form.html'
    success_url = reverse_lazy('grn_list')

    def dispatch(self, request, *args, **kwargs):
        if self.get_object().status != GRN.StatusChoices.DRAFT:
            messages.error(request, "Only Draft GRNs can be edited.")
            return redirect('grn_list')
        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        data = super().get_context_data(**kwargs)
        if self.request.POST:
            data['items'] = GRNItemFormSet(self.request.POST, instance=self.object)
        else:
            data['items'] = GRNItemFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        items = context['items']
        
        if items.is_valid():
            self.object = form.save()
            items.instance = self.object
            items.save()
            messages.success(self.request, f"GRN {self.object.grn_number} updated.")
            return redirect(self.success_url)
        else:
            return self.render_to_response(self.get_context_data(form=form))

@login_required
def confirm_grn_view(request, pk):
    grn = get_object_or_404(GRN, pk=pk)
    if request.method == 'POST':
        try:
            confirm_grn(grn, request.user)
            messages.success(request, f"GRN {grn.grn_number} successfully confirmed. Stock updated.")
        except Exception as e:
            messages.error(request, f"Error confirming GRN: {str(e)}")
    return redirect('grn_list')

@login_required
def cancel_grn_view(request, pk):
    grn = get_object_or_404(GRN, pk=pk)
    if request.method == 'POST':
        try:
            cancel_grn(grn, request.user)
            messages.success(request, f"GRN {grn.grn_number} successfully cancelled. Stock reversed.")
        except Exception as e:
            messages.error(request, f"Error cancelling GRN: {str(e)}")
    return redirect('grn_list')
