import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

import sales.views
import sales.services
import visits.views
import purchases.views

print("Syntax and imports successful.")
