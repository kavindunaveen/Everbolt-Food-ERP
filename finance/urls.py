from django.urls import path
from .views import (
    FinanceDashboardView, OverdueInvoicesView, RecordPaymentView, AgedReceivablesView,
    ChartOfAccountsView, AccountCreateView, JournalEntryListView, JournalEntryCreateView, GeneralLedgerView
)

urlpatterns = [
    path('', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('overdue/', OverdueInvoicesView.as_view(), name='finance_overdue_invoices'),
    path('api/record-payment/', RecordPaymentView.as_view(), name='finance_record_payment'),
    path('aged-receivables/', AgedReceivablesView.as_view(), name='finance_aged_receivables'),
    path('chart-of-accounts/', ChartOfAccountsView.as_view(), name='finance_chart_of_accounts'),
    path('chart-of-accounts/add/', AccountCreateView.as_view(), name='finance_account_create'),
    path('journal-entries/', JournalEntryListView.as_view(), name='finance_journal_entries'),
    path('journal-entries/add/', JournalEntryCreateView.as_view(), name='finance_journal_entry_create'),
    path('general-ledger/', GeneralLedgerView.as_view(), name='finance_general_ledger'),
]
