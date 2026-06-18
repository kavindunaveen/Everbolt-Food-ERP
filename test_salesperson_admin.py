import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from django.test import Client
from users.models import User

admin_sp = User.objects.get(username='admin')
client = Client(HTTP_HOST='localhost')
client.force_login(admin_sp)

response = client.get(f'/dashboard/api/salesperson/?salesperson_id={admin_sp.id}&date_from=2026-06-01&date_to=2026-06-30', HTTP_HOST='localhost')
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"Response: {response.content.decode()}")
else:
    print(f"Response: {response.content.decode()}")
