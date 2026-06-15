from django.urls import path
from .views import FinanceDashboardView, OverdueInvoicesView, RecordPaymentView, AgedReceivablesView

urlpatterns = [
    path('', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('overdue/', OverdueInvoicesView.as_view(), name='finance_overdue_invoices'),
    path('api/record-payment/', RecordPaymentView.as_view(), name='finance_record_payment'),
    path('aged-receivables/', AgedReceivablesView.as_view(), name='finance_aged_receivables'),
]
