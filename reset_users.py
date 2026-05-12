import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from users.models import User

# Delete all users except 'admin'
User.objects.exclude(username='admin').delete()

# Ensure 'admin' exists and has the right credentials
admin_user, created = User.objects.get_or_create(username='admin')
admin_user.set_password('kavindu123')
admin_user.is_superuser = True
admin_user.is_staff = True
admin_user.role = User.Roles.ADMIN
admin_user.save()

print(f"User 'admin' {'created' if created else 'updated'}. All other users deleted.")
