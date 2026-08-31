from django.urls import path
from .views import (
    FinanceDashboardView, PendingPaymentsView, PartialPaymentsView, CompletedPaymentsView, RecordPaymentView, AgedReceivablesView,
    ChartOfAccountsView, AccountCreateView, JournalEntryListView, JournalEntryDetailView, JournalEntryCreateView, GeneralLedgerView,
    CustomerCreditListView, apply_customer_credit,
    ReconciliationView, ReconcilePaymentView, BulkReconcileView,
    BankAccountListView, BankAccountCreateView, BankAccountUpdateView, BankAccountDeleteView,
)

urlpatterns = [
    path('', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('bank-accounts/', BankAccountListView.as_view(), name='finance_bank_accounts'),
    path('bank-accounts/add/', BankAccountCreateView.as_view(), name='finance_bank_account_create'),
    path('bank-accounts/<int:pk>/edit/', BankAccountUpdateView.as_view(), name='finance_bank_account_edit'),
    path('bank-accounts/<int:pk>/delete/', BankAccountDeleteView.as_view(), name='finance_bank_account_delete'),
    path('pending-payments/', PendingPaymentsView.as_view(), name='finance_pending_payments'),
    path('partial-payments/', PartialPaymentsView.as_view(), name='finance_partial_payments'),
    path('completed-payments/', CompletedPaymentsView.as_view(), name='finance_completed_payments'),
    path('api/record-payment/', RecordPaymentView.as_view(), name='finance_record_payment'),
    path('aged-receivables/', AgedReceivablesView.as_view(), name='finance_aged_receivables'),
    path('chart-of-accounts/', ChartOfAccountsView.as_view(), name='finance_chart_of_accounts'),
    path('chart-of-accounts/add/', AccountCreateView.as_view(), name='finance_account_create'),
    path('journal-entries/', JournalEntryListView.as_view(), name='finance_journal_entries'),
    path('journal-entries/<int:pk>/', JournalEntryDetailView.as_view(), name='finance_journal_entry_detail'),
    path('journal-entries/add/', JournalEntryCreateView.as_view(), name='finance_journal_entry_create'),
    path('general-ledger/', GeneralLedgerView.as_view(), name='finance_general_ledger'),
    path('customer-credits/', CustomerCreditListView.as_view(), name='finance_customer_credits'),
    path('api/apply-customer-credit/', apply_customer_credit, name='finance_apply_customer_credit'),
    # Reconciliation
    path('reconciliation/', ReconciliationView.as_view(), name='finance_reconciliation'),
    path('api/reconcile-payment/', ReconcilePaymentView.as_view(), name='finance_reconcile_payment'),
    path('api/bulk-reconcile/', BulkReconcileView.as_view(), name='finance_bulk_reconcile'),
]
