from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, DetailView, View
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse
from django.utils.decorators import method_decorator
from django.db.models import Q, Sum

from inventory.models import Product
from users.models import User
from .models import (
    WebsiteSettings, WebsiteCategory, WebsiteProduct, WebsitePage, WebsiteEnquiry, WebsiteOrder, WebsiteHeroSlide, SEORedirect, WebsiteBlogPost
)
from .forms import (
    WebsiteSettingsForm, WebsiteCategoryForm, WebsiteProductForm,
    WebsitePageForm, WebsiteEnquiryNotesForm, WebsiteHeroSlideForm, SEORedirectForm, WebsiteBlogPostForm
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

    total_orders = WebsiteOrder.objects.count()
    new_orders_count = WebsiteOrder.objects.filter(sync_status='pending').count()
    recent_orders = WebsiteOrder.objects.order_by('-created_at')[:5]

    # Products not yet listed on the website
    listed_ids = WebsiteProduct.objects.values_list('inventory_product_id', flat=True)
    unlisted_count = Product.objects.filter(status=True).exclude(pk__in=listed_ids).count()

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
        'total_orders': total_orders,
        'new_orders_count': new_orders_count,
        'recent_orders': recent_orders,
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


from django.forms import inlineformset_factory
from .models import WebsiteProductVariant
from inventory.models import Product

VariantFormSet = inlineformset_factory(
    WebsiteProduct, WebsiteProductVariant,
    fields=('inventory_product', 'variant_name', 'display_order'),
    extra=1,
    can_delete=True
)

class WebsiteProductCreateView(LoginRequiredMixin, CreateView):
    model = WebsiteProduct
    form_class = WebsiteProductForm
    template_name = 'website/product_form.html'
    success_url = reverse_lazy('website_product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        listed_ids = WebsiteProduct.objects.values_list('inventory_product_id', flat=True)
        ctx['unlisted_products'] = Product.objects.filter(status=True).exclude(pk__in=listed_ids).order_by('category', 'name')
        if self.request.POST:
            ctx['variant_formset'] = VariantFormSet(self.request.POST)
        else:
            ctx['variant_formset'] = VariantFormSet()
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        variant_formset = context['variant_formset']
        if form.is_valid() and variant_formset.is_valid():
            self.object = form.save()
            variant_formset.instance = self.object
            variant_formset.save()
            messages.success(self.request, f'Product "{self.object.get_display_name()}" added to website.')
            return super().form_valid(form)
        else:
            return self.form_invalid(form)


class WebsiteProductEditView(LoginRequiredMixin, UpdateView):
    model = WebsiteProduct
    form_class = WebsiteProductForm
    template_name = 'website/product_form.html'
    success_url = reverse_lazy('website_product_list')

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        if self.request.POST:
            ctx['variant_formset'] = VariantFormSet(self.request.POST, instance=self.object)
        else:
            ctx['variant_formset'] = VariantFormSet(instance=self.object)
        return ctx

    def form_valid(self, form):
        context = self.get_context_data()
        variant_formset = context['variant_formset']
        if form.is_valid() and variant_formset.is_valid():
            self.object = form.save()
            variant_formset.instance = self.object
            variant_formset.save()
            messages.success(self.request, f'Product "{self.object.get_display_name()}" updated.')
            return super().form_valid(form)
        else:
            return self.form_invalid(form)

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


# ─── Hero Slides ───────────────────────────────────────────────────────────────

class WebsiteHeroSlideListView(LoginRequiredMixin, ListView):
    model = WebsiteHeroSlide
    template_name = 'website/slide_list.html'
    context_object_name = 'slides'

class WebsiteHeroSlideCreateView(LoginRequiredMixin, CreateView):
    model = WebsiteHeroSlide
    form_class = WebsiteHeroSlideForm
    template_name = 'website/slide_form.html'
    success_url = reverse_lazy('website_slide_list')

    def form_valid(self, form):
        messages.success(self.request, 'Hero slide added successfully.')
        return super().form_valid(form)

class WebsiteHeroSlideEditView(LoginRequiredMixin, UpdateView):
    model = WebsiteHeroSlide
    form_class = WebsiteHeroSlideForm
    template_name = 'website/slide_form.html'
    success_url = reverse_lazy('website_slide_list')

    def form_valid(self, form):
        messages.success(self.request, 'Hero slide updated successfully.')
        return super().form_valid(form)

class WebsiteHeroSlideDeleteView(LoginRequiredMixin, DeleteView):
    model = WebsiteHeroSlide
    success_url = reverse_lazy('website_slide_list')

    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Hero slide deleted successfully.')
        return super().delete(request, *args, **kwargs)


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


# ─── Blog Posts ─────────────────────────────────────────────────────────────────

class WebsiteBlogListView(LoginRequiredMixin, ListView):
    model = WebsiteBlogPost
    template_name = 'website/blog_list.html'
    context_object_name = 'posts'
    paginate_by = 20

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get('q')
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(author__icontains=q))
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs.order_by('-created_at')


class WebsiteBlogCreateView(LoginRequiredMixin, CreateView):
    model = WebsiteBlogPost
    form_class = WebsiteBlogPostForm
    template_name = 'website/blog_form.html'
    success_url = reverse_lazy('website_blog_list')

    def form_valid(self, form):
        messages.success(self.request, f'Blog post "{form.instance.title}" created.')
        return super().form_valid(form)


class WebsiteBlogEditView(LoginRequiredMixin, UpdateView):
    model = WebsiteBlogPost
    form_class = WebsiteBlogPostForm
    template_name = 'website/blog_form.html'
    success_url = reverse_lazy('website_blog_list')

    def form_valid(self, form):
        messages.success(self.request, f'Blog post "{form.instance.title}" updated.')
        return super().form_valid(form)


class WebsiteBlogDeleteView(LoginRequiredMixin, DeleteView):
    model = WebsiteBlogPost
    template_name = 'website/blog_confirm_delete.html'
    success_url = reverse_lazy('website_blog_list')

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        messages.success(request, f'Blog post "{obj.title}" deleted.')
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

# ─── Orders ───────────────────────────────────────────────────────────────────

class WebsiteOrderListView(LoginRequiredMixin, ListView):
    model = WebsiteOrder
    template_name = 'website/order_list.html'
    paginate_by = 20
    ordering = ['-created_at']

class WebsiteOrderDetailView(LoginRequiredMixin, DetailView):
    model = WebsiteOrder
    template_name = 'website/order_detail.html'

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        old_status = self.object.sync_status
        new_status = request.POST.get('sync_status')
        
        if old_status in ['cancelled']:
            messages.error(request, f"This order is already {old_status} and its status cannot be changed.")
            return redirect('website_order_list')
        
        if new_status in dict(WebsiteOrder.SYNC_STATUS_CHOICES) and old_status != new_status:
            self.object.sync_status = new_status
            self.object.save()
            # Removed conversion logic
            
            # 2. Cancellation Logic (Release Stock)
            if new_status == 'cancelled':
                from inventory.models import StockReserve
                StockReserve.objects.filter(reference_type='WEB_ORDER', reference_id=self.object.pk).delete()
            
            # 3. Email Notification Logic
            if new_status in ['dispatched', 'delivered', 'cancelled']:
                import threading
                from django.template.loader import render_to_string
                from django.core.mail import EmailMultiAlternatives
                from django.conf import settings

                def send_status_email(order, status):
                    if not order.email: return
                    subject = f"Order {status.title()} - {order.website_order_number}"
                    from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@organicfoodslanka.com')
                    context = {'order': order, 'status': status}
                    
                    text_content = render_to_string('emails/order_status_update.txt', context)
                    html_content = render_to_string('emails/order_status_update.html', context)
                    
                    msg = EmailMultiAlternatives(subject, text_content, from_email, [order.email])
                    msg.attach_alternative(html_content, "text/html")
                    msg.send(fail_silently=True)
                
                threading.Thread(target=send_status_email, args=(self.object, new_status)).start()
            
            if new_status != 'converted':
                messages.success(request, f"Order status updated to {self.object.get_sync_status_display()}")
                
        return redirect('website_order_list')

# ─── Customers ─────────────────────────────────────────────────────────────────

class WebsiteCustomerListView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'website/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        qs = User.objects.filter(role__name='Website Customer').order_by('-date_joined')
        q = self.request.GET.get('q', '')
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(email__icontains=q))
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx['q'] = self.request.GET.get('q', '')
        return ctx

class WebsiteCustomerDetailView(LoginRequiredMixin, DetailView):
    model = User
    template_name = 'website/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        user = self.get_object()
        orders = WebsiteOrder.objects.filter(user=user).order_by('-created_at')
        ctx['orders'] = orders
        ctx['lifetime_value'] = orders.filter(sync_status__in=['pending', 'converted']).aggregate(total=Sum('total_amount'))['total'] or 0
        return ctx

# ─── SEO Redirects ─────────────────────────────────────────────────────────────

class SEORedirectListView(LoginRequiredMixin, ListView):
    model = SEORedirect
    template_name = 'website/redirect_list.html'
    context_object_name = 'redirects'

class SEORedirectCreateView(LoginRequiredMixin, CreateView):
    model = SEORedirect
    form_class = SEORedirectForm
    template_name = 'website/redirect_form.html'
    success_url = reverse_lazy('website_redirect_list')

    def form_valid(self, form):
        messages.success(self.request, "SEO Redirect created successfully.")
        return super().form_valid(form)

class SEORedirectUpdateView(LoginRequiredMixin, UpdateView):
    model = SEORedirect
    form_class = SEORedirectForm
    template_name = 'website/redirect_form.html'
    success_url = reverse_lazy('website_redirect_list')

    def form_valid(self, form):
        messages.success(self.request, "SEO Redirect updated successfully.")
        return super().form_valid(form)

class SEORedirectDeleteView(LoginRequiredMixin, DeleteView):
    model = SEORedirect
    template_name = 'website/redirect_confirm_delete.html'
    success_url = reverse_lazy('website_redirect_list')

    def delete(self, request, *args, **kwargs):
        messages.success(self.request, "SEO Redirect deleted.")
        return super().delete(request, *args, **kwargs)

