from django.urls import path
from . import views

urlpatterns = [
    path('', views.FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('overdue/', views.OverdueInvoicesView.as_view(), name='finance_overdue_invoices'),
    path('api/record-payment/', views.RecordPaymentView.as_view(), name='finance_record_payment'),
]
