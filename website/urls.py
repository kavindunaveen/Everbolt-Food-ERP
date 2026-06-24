from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('', views.website_dashboard, name='website_dashboard'),

    # Products
    path('products/', views.WebsiteProductListView.as_view(), name='website_product_list'),
    path('products/add/', views.WebsiteProductCreateView.as_view(), name='website_product_add'),
    path('products/<int:pk>/edit/', views.WebsiteProductEditView.as_view(), name='website_product_edit'),
    path('products/<int:pk>/toggle/', views.toggle_product_status, name='website_product_toggle'),

    # Hero Slides
    path('slides/', views.WebsiteHeroSlideListView.as_view(), name='website_slide_list'),
    path('slides/add/', views.WebsiteHeroSlideCreateView.as_view(), name='website_slide_add'),
    path('slides/<int:pk>/edit/', views.WebsiteHeroSlideEditView.as_view(), name='website_slide_edit'),
    path('slides/<int:pk>/delete/', views.WebsiteHeroSlideDeleteView.as_view(), name='website_slide_delete'),

    # Categories
    path('categories/', views.WebsiteCategoryListView.as_view(), name='website_category_list'),
    path('categories/add/', views.WebsiteCategoryCreateView.as_view(), name='website_category_add'),
    path('categories/<int:pk>/edit/', views.WebsiteCategoryEditView.as_view(), name='website_category_edit'),
    path('categories/<int:pk>/delete/', views.WebsiteCategoryDeleteView.as_view(), name='website_category_delete'),

    # Pages
    path('pages/', views.WebsitePageListView.as_view(), name='website_page_list'),
    path('pages/add/', views.WebsitePageCreateView.as_view(), name='website_page_add'),
    path('pages/<int:pk>/edit/', views.WebsitePageEditView.as_view(), name='website_page_edit'),
    path('pages/<int:pk>/delete/', views.WebsitePageDeleteView.as_view(), name='website_page_delete'),

    # Orders
    path('orders/', views.WebsiteOrderListView.as_view(), name='website_order_list'),
    path('orders/<int:pk>/', views.WebsiteOrderDetailView.as_view(), name='website_order_detail'),

    # Customers
    path('customers/', views.WebsiteCustomerListView.as_view(), name='website_customer_list'),
    path('customers/<int:pk>/', views.WebsiteCustomerDetailView.as_view(), name='website_customer_detail'),

    # Enquiries
    path('enquiries/', views.WebsiteEnquiryListView.as_view(), name='website_enquiry_list'),
    path('enquiries/<int:pk>/', views.WebsiteEnquiryDetailView.as_view(), name='website_enquiry_detail'),

    # Settings
    path('settings/', views.WebsiteSettingsView.as_view(), name='website_settings'),

    # SEO Redirects
    path('redirects/', views.SEORedirectListView.as_view(), name='website_redirect_list'),
    path('redirects/add/', views.SEORedirectCreateView.as_view(), name='website_redirect_add'),
    path('redirects/<int:pk>/edit/', views.SEORedirectUpdateView.as_view(), name='website_redirect_edit'),
    path('redirects/<int:pk>/delete/', views.SEORedirectDeleteView.as_view(), name='website_redirect_delete'),
]
