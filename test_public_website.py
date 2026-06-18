import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from django.test import Client

c = Client(SERVER_NAME='localhost')
response = c.get("/public/")
print(f"Status Code: {response.status_code}")
if response.status_code != 200:
    print(response.content.decode('utf-8')[:500])
