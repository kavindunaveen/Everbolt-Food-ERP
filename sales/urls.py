from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='sales/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),
    
    path('', views.MainDashboardView.as_view(), name='main_dashboard'),
    path('sales/', views.SalesDashboardView.as_view(), name='sales_dashboard'),
    path('sales/quotations/', views.QuotationListView.as_view(), name='quotation_list'),
    path('sales/quotations/new/', views.QuotationCreateView.as_view(), name='quotation_create'),
    path('sales/quotations/<int:pk>/edit/', views.QuotationUpdateView.as_view(), name='quotation_edit'),
    path('sales/quotations/export/', views.QuotationExportView.as_view(), name='quotation_export'),
    path('sales/invoices/', views.InvoiceListView.as_view(), name='invoice_list'),
    path('sales/invoices/new/', views.InvoiceCreateView.as_view(), name='invoice_create'),
    path('sales/invoices/<int:pk>/edit/', views.InvoiceUpdateView.as_view(), name='invoice_edit'),
    path('sales/invoices/export/', views.InvoiceExportView.as_view(), name='invoice_export'),
    
    path('sales/quotations/<int:pk>/print/', views.QuotationPrintView.as_view(), name='quotation_print'),
    path('sales/invoices/<int:pk>/print/', views.InvoicePrintView.as_view(), name='invoice_print'),
    path('sales/invoices/<int:pk>/confirm/', views.confirm_invoice_view, name='invoice_confirm'),
    path('sales/invoices/<int:pk>/cancel/', views.cancel_invoice_view, name='invoice_cancel'),
    path('sales/invoices/<int:pk>/request-edit/', views.request_edit_invoice_view, name='invoice_request_edit'),
    path('sales/invoices/<int:pk>/approve/', views.approve_invoice_view, name='invoice_approve'),
    path('sales/invoices/<int:pk>/reject/', views.reject_invoice_view, name='invoice_reject'),
    path('sales/quotations/<int:pk>/mark-sent/', views.quotation_mark_sent_view, name='quotation_mark_sent'),
    path('sales/quotations/<int:pk>/cancel/', views.quotation_cancel_view, name='quotation_cancel'),
    path('sales/quotations/<int:pk>/convert/', views.convert_quotation_view, name='quotation_convert'),
    
    # AJAX Search Endpoints
    path('api/customers/search/', views.customer_search_ajax, name='customer_search_ajax'),
    path('api/products/search/', views.product_search_ajax, name='product_search_ajax'),

    # Delivery Note URLs
    path('sales/delivery-notes/', views.DeliveryNoteListView.as_view(), name='delivery_note_list'),
    path('sales/delivery-notes/new/', views.DeliveryNoteCreateView.as_view(), name='delivery_note_create'),
    path('sales/delivery-notes/<int:pk>/', views.DeliveryNoteDetailView.as_view(), name='delivery_note_detail'),
    path('sales/delivery-notes/<int:pk>/update-status/', views.update_dn_status, name='delivery_note_update_status'),
    path('api/invoices/<int:pk>/details/', views.get_invoice_details, name='get_invoice_details'),
]
