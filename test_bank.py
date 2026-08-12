import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from finance.models import BankAccount, Account
boc = BankAccount.objects.create(bank_name='BOC', account_number='12345678', branch='Colombo', ledger_account=Account.objects.get(code='1010'))
print(f'Created {boc}')
