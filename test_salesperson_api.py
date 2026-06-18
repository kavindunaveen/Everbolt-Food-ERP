import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from django.test import Client
from users.models import User

sp = User.objects.filter(role__name='Sales Officer').first()
if not sp:
    sp = User.objects.first()

client = Client(HTTP_HOST='localhost')
client.force_login(sp)

response = client.get(f'/dashboard/api/salesperson/?salesperson_id={sp.id}&all_time=true', HTTP_HOST='localhost')
print(f"Status Code: {response.status_code}")
if response.status_code == 200:
    print(f"Content Length: {len(response.content)}")
    print(f"Snippet: {response.content.decode()[:500]}")
else:
    print(f"Response: {response.content.decode()}")

