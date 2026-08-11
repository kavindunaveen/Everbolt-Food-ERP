import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'sales_erp.settings')
django.setup()
from django.core.exceptions import ValidationError
print(ValidationError({'qty': 'message'}).error_dict)
