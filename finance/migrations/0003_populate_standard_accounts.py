from django.db import migrations

def populate_accounts(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    
    standard_accounts = [
        # Assets
        ('1000', 'Cash', 'ASSET'),
        ('1010', 'Bank Account', 'ASSET'),
        ('1200', 'Accounts Receivable', 'ASSET'),
        ('1300', 'Inventory', 'ASSET'),
        # Liabilities
        ('2000', 'Accounts Payable', 'LIABILITY'),
        ('2100', 'Sales Tax Payable', 'LIABILITY'),
        # Equity
        ('3000', 'Owners Equity', 'EQUITY'),
        ('3100', 'Retained Earnings', 'EQUITY'),
        # Revenue
        ('4000', 'Sales Revenue', 'REVENUE'),
        ('4100', 'Service Revenue', 'REVENUE'),
        # Expenses
        ('5000', 'Cost of Goods Sold', 'EXPENSE'),
        ('6000', 'Salary Expense', 'EXPENSE'),
        ('6100', 'Rent Expense', 'EXPENSE'),
        ('6200', 'Utilities Expense', 'EXPENSE'),
        ('6300', 'Office Supplies', 'EXPENSE'),
        ('6400', 'Marketing & Advertising', 'EXPENSE'),
    ]
    
    for code, name, account_type in standard_accounts:
        Account.objects.get_or_create(code=code, defaults={
            'name': name,
            'account_type': account_type,
            'is_active': True
        })

def reverse_accounts(apps, schema_editor):
    Account = apps.get_model('finance', 'Account')
    Account.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        ('finance', '0002_account_alter_payment_options_journalentry_and_more'),
    ]

    operations = [
        migrations.RunPython(populate_accounts, reverse_accounts),
    ]
