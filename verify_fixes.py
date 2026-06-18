import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from django.test import Client
from users.models import User
from sales.models import Invoice, Quotation
from inventory.models import Product
from django.urls import reverse

def verify():
    # Verify JSON exceptions
    c = Client()
    # Find a user to log in
    user = User.objects.filter(is_superuser=True).first()
    if user:
        c.force_login(user)

    # 1. Test visits/views.py save_plan (Should return 400 with 'status': 'error', not 500)
    print("Testing /visits/plan/save/ with bad JSON...")
    response = c.post('/visits/plan/save/', "BAD JSON DATA", content_type="application/json")
    print(f"visits/plan/save status code: {response.status_code}") # Expect 400
    if response.status_code == 400:
        print("PASS: JSON exception handled gracefully in visits.")
    else:
        print(f"FAIL: Expected 400, got {response.status_code}")

    # 2. Verify N+1 select_related syntax in views (Querying the view)
    print("\nTesting /sales/invoices/ syntax...")
    response = c.get('/sales/invoices/')
    print(f"Invoice list status code: {response.status_code}")
    if response.status_code == 200:
        print("PASS: InvoiceListView loaded successfully (select_related is working).")
    else:
        print("FAIL: InvoiceListView failed to load.")

verify()
