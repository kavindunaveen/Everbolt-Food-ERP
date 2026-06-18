import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sales_erp.settings")
django.setup()

from users.models import User

users = User.objects.values('id', 'username', 'role__name')
print("Users:", list(users))
