from django.urls import path
from .views import (
    FinanceDashboardView, PendingPaymentsView, PartialPaymentsView, CompletedPaymentsView, RecordPaymentView, AgedReceivablesView,
    ChartOfAccountsView, AccountCreateView, JournalEntryListView, JournalEntryCreateView, GeneralLedgerView,
    CustomerCreditListView, apply_customer_credit
)

urlpatterns = [
    path('', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('pending-payments/', PendingPaymentsView.as_view(), name='finance_pending_payments'),
    path('partial-payments/', PartialPaymentsView.as_view(), name='finance_partial_payments'),
    path('completed-payments/', CompletedPaymentsView.as_view(), name='finance_completed_payments'),
    path('api/record-payment/', RecordPaymentView.as_view(), name='finance_record_payment'),
    path('aged-receivables/', AgedReceivablesView.as_view(), name='finance_aged_receivables'),
    path('chart-of-accounts/', ChartOfAccountsView.as_view(), name='finance_chart_of_accounts'),
    path('chart-of-accounts/add/', AccountCreateView.as_view(), name='finance_account_create'),
    path('journal-entries/', JournalEntryListView.as_view(), name='finance_journal_entries'),
    path('journal-entries/add/', JournalEntryCreateView.as_view(), name='finance_journal_entry_create'),
    path('general-ledger/', GeneralLedgerView.as_view(), name='finance_general_ledger'),
    path('customer-credits/', CustomerCreditListView.as_view(), name='finance_customer_credits'),
    path('api/apply-customer-credit/', apply_customer_credit, name='finance_apply_customer_credit'),
]
