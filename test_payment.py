import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from finance.models import BankAccount, Account, JournalEntry, Payment
from sales.models import Invoice
from django.contrib.auth import get_user_model
from datetime import date
User = get_user_model()
user = User.objects.first()
inv = Invoice.objects.filter(status='ISSUED').first()
if inv:
  print(f'Testing with Invoice {inv.invoice_number}')
  boc = BankAccount.objects.first()
  je_count_before = JournalEntry.objects.count()
  from django.test import RequestFactory
  from finance.views import RecordPaymentView
  request = RequestFactory().post('/finance/pending-payments/', {'invoice_id': inv.id, 'amount': '150.00', 'payment_date': '2026-08-12', 'payment_method': 'BANK_TRANSFER', 'bank_account_id': boc.id, 'reference': 'TESTREF01'})
  request.user = user
  view = RecordPaymentView.as_view()
  response = view(request)
  print(f'Response status: {response.status_code}, content: {response.content}')
  je_count_after = JournalEntry.objects.count()
  print(f'Journal Entries created: {je_count_after - je_count_before}')
  je = JournalEntry.objects.last()
  print(f'Last JE: {je.reference}')
  for line in je.lines.all():
    print(f'  {line.account.name}: Debit={line.debit}, Credit={line.credit}')
else:
  print('No ISSUED invoice found.')
