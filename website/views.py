from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db.models import Q

from inventory.models import Product
from .models import WebsiteSettings, WebsiteCategory, WebsiteProduct, WebsitePage, WebsiteEnquiry
from .forms import (
    WebsiteSettingsForm, WebsiteCategoryForm, WebsiteProductForm,
    WebsitePageForm, WebsiteEnquiryNotesForm
)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@login_required
def website_dashboard(request):
    total_products = WebsiteProduct.objects.count()
    published_products = WebsiteProduct.objects.filter(status=WebsiteProduct.Status.PUBLISHED).count()
    draft_products = WebsiteProduct.objects.filter(status=WebsiteProduct.Status.DRAFT).count()
    total_pages = WebsitePage.objects.count()
    published_pages = WebsitePage.objects.filter(status=WebsitePage.Status.PUBLISHED).count()
    new_enquiries = WebsiteEnquiry.objects.filter(status=WebsiteEnquiry.Status.NEW).count()
    total_enquiries = WebsiteEnquiry.objects.count()
    total_categories = WebsiteCategory.objects.count()
    featured_products = WebsiteProduct.objects.filter(is_featured=True, status=WebsiteProduct.Status.PUBLISHED).count()
    recent_enquiries = WebsiteEnquiry.objects.filter(status=WebsiteEnquiry.Status.NEW).order_by('-submitted_at')[:5]
    settings = WebsiteSettings.get_settings()

    # Products not yet listed on the website
    listed_ids = WebsiteProduct.objects.values_list('inventory_product_id', flat=True)
    unlisted_count = Product.objects.exclude(pk__in=listed_ids).count()

    context = {
        'total_products': total_products,
        'published_products': published_products,
        'draft_products': draft_products,
        'total_pages': total_pages,
        'published_pages': published_pages,
        'new_enquiries': new_enquiries,
        'total_enquiries': total_enquiries,
        'total_categories': total_categories,
        'featured_products': featured_products,
        'recent_enquiries': recent_enquiries,
        'settings': settings,
        'unlisted_count': unlisted_count,
    }
    return render(request, 'website/dashboard.html', context)


# ─── Products ─────────────────────────────────────────────────────────────────

class WebsiteProductListView(LoginRequiredMixin, ListView):
    model = WebsiteProduct
    template_name = 'website/product_list.html'
    context_object_name = 'products'
    paginate_by = 25

    def get_queryset(self):
        qs = WebsiteProduct.objects.select_related('inventory_product', 'website_category')
        q = self.request.GET.get('q', '')
        status = self.request.GET.get('status', '')
        category = self.request.GET.get('category', '')
        if q:
            qs = qs.filter(
                Q(display_name__icontains=q) |
                Q(inventory_product__name__icontains=q)
            )
        if status:
            qs = qs.filter(status=status)
        if category:
            qs = qs.filter(website_category_id=category)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['categories'] = WebsiteCategory.objects.all()
        ctx['status_choices'] = WebsiteProduct.Status.choices
        ctx['q'] = self.request.GET.get('q', '')
        ctx['selected_status'] = self.request.GET.get('status', '')
        ctx['selected_category'] = self.request.GET.get('category', '')
        return ctx


class WebsiteProductCreateView(LoginRequiredMixin, CreateView):
    model = WebsiteProduct
    form_class = WebsiteProductForm
    template_name = 'website/product_form.html'
    success_url = reverse_lazy('website_product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        # Show only inventory products not yet listed
        listed_ids = WebsiteProduct.objects.values_list('inventory_product_id', flat=True)
        ctx['unlisted_products'] = Product.objects.exclude(pk__in=listed_ids).order_by('category', 'name')
        return ctx

    def form_valid(self, form):
        messages.success(self.request, f'Product "{form.instance.get_display_name()}" added to website.')
        return super().form_valid(form)


class WebsiteProductEditView(LoginRequiredMixin, UpdateView):
    model = WebsiteProduct
    form_class = WebsiteProductForm
    template_name = 'website/product_form.html'
    success_url = reverse_lazy('website_product_list')

    def form_valid(self, form):
        messages.success(self.request, f'Product "{form.instance.get_display_name()}" updated.')
        return super().form_valid(form)


@login_required
def toggle_product_status(request, pk):
    product = get_object_or_404(WebsiteProduct, pk=pk)
    if product.status == WebsiteProduct.Status.PUBLISHED:
        product.status = WebsiteProduct.Status.HIDDEN
        messages.warning(request, f'"{product.get_display_name()}" hidden from website.')
    else:
        product.status = WebsiteProduct.Status.PUBLISHED
        messages.success(request, f'"{product.get_display_name()}" is now published on the website.')
    product.save(update_fields=['status'])
    return redirect('website_product_list')


# ─── Categories ───────────────────────────────────────────────────────────────

class WebsiteCategoryListView(LoginRequiredMixin, ListView):
    model = WebsiteCategory
    template_name = 'website/category_list.html'
    context_object_name = 'categories'


class WebsiteCategoryCreateView(LoginRequiredMixin, CreateView):
    model = WebsiteCategory
    form_class = WebsiteCategoryForm
    template_name = 'website/category_form.html'
    success_url = reverse_lazy('website_category_list')

    def form_valid(self, form):
        messages.success(self.request, f'Category "{form.instance.name}" created.')
        return super().form_valid(form)


class WebsiteCategoryEditView(LoginRequiredMixin, UpdateView):
    model = WebsiteCategory
    form_class = WebsiteCategoryForm
    template_name = 'website/category_form.html'
    success_url = reverse_lazy('website_category_list')

    def form_valid(self, form):
        messages.success(self.request, f'Category "{form.instance.name}" updated.')
        return super().form_valid(form)


class WebsiteCategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = WebsiteCategory
    success_url = reverse_lazy('website_category_list')

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f'Category "{obj.name}" deleted.')
        return super().post(request, *args, **kwargs)


# ─── Pages ────────────────────────────────────────────────────────────────────

class WebsitePageListView(LoginRequiredMixin, ListView):
    model = WebsitePage
    template_name = 'website/page_list.html'
    context_object_name = 'pages'


class WebsitePageCreateView(LoginRequiredMixin, CreateView):
    model = WebsitePage
    form_class = WebsitePageForm
    template_name = 'website/page_form.html'
    success_url = reverse_lazy('website_page_list')

    def form_valid(self, form):
        messages.success(self.request, f'Page "{form.instance.title}" created.')
        return super().form_valid(form)


class WebsitePageEditView(LoginRequiredMixin, UpdateView):
    model = WebsitePage
    form_class = WebsitePageForm
    template_name = 'website/page_form.html'
    success_url = reverse_lazy('website_page_list')

    def form_valid(self, form):
        messages.success(self.request, f'Page "{form.instance.title}" updated.')
        return super().form_valid(form)


class WebsitePageDeleteView(LoginRequiredMixin, DeleteView):
    model = WebsitePage
    success_url = reverse_lazy('website_page_list')

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f'Page "{obj.title}" deleted.')
        return super().post(request, *args, **kwargs)


# ─── Enquiries ────────────────────────────────────────────────────────────────

class WebsiteEnquiryListView(LoginRequiredMixin, ListView):
    model = WebsiteEnquiry
    template_name = 'website/enquiry_list.html'
    context_object_name = 'enquiries'
    paginate_by = 30

    def get_queryset(self):
        qs = WebsiteEnquiry.objects.all()
        status = self.request.GET.get('status', '')
        q = self.request.GET.get('q', '')
        if status:
            qs = qs.filter(status=status)
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(email__icontains=q) | Q(subject__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['status_choices'] = WebsiteEnquiry.Status.choices
        ctx['new_count'] = WebsiteEnquiry.objects.filter(status=WebsiteEnquiry.Status.NEW).count()
        ctx['q'] = self.request.GET.get('q', '')
        ctx['selected_status'] = self.request.GET.get('status', '')
        return ctx


class WebsiteEnquiryDetailView(LoginRequiredMixin, UpdateView):
    model = WebsiteEnquiry
    form_class = WebsiteEnquiryNotesForm
    template_name = 'website/enquiry_detail.html'
    success_url = reverse_lazy('website_enquiry_list')

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        # Auto mark as in-progress when opened
        if obj.status == WebsiteEnquiry.Status.NEW:
            obj.status = WebsiteEnquiry.Status.IN_PROGRESS
            obj.save(update_fields=['status'])
        return obj

    def form_valid(self, form):
        messages.success(self.request, 'Enquiry updated.')
        return super().form_valid(form)


# ─── Settings ─────────────────────────────────────────────────────────────────

class WebsiteSettingsView(LoginRequiredMixin, View):
    template_name = 'website/settings.html'

    def get(self, request):
        settings = WebsiteSettings.get_settings()
        form = WebsiteSettingsForm(instance=settings)
        return render(request, self.template_name, {'form': form, 'settings': settings})

    def post(self, request):
        settings = WebsiteSettings.get_settings()
        form = WebsiteSettingsForm(request.POST, instance=settings)
        if form.is_valid():
            form.save()
            messages.success(request, 'Website settings saved successfully.')
            return redirect('website_settings')
        return render(request, self.template_name, {'form': form, 'settings': settings})
