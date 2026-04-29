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

    # Enquiries
    path('enquiries/', views.WebsiteEnquiryListView.as_view(), name='website_enquiry_list'),
    path('enquiries/<int:pk>/', views.WebsiteEnquiryDetailView.as_view(), name='website_enquiry_detail'),

    # Settings
    path('settings/', views.WebsiteSettingsView.as_view(), name='website_settings'),
]
