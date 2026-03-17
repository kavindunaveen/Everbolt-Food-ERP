from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Seeds the database with the initial Sales Officer accounts'

    def handle(self, *args, **kwargs):
        officers = [
            {'username': 'keshan', 'first_name': 'Keshan', 'assigned_area': 'Region A'},
            {'username': 'manisha', 'first_name': 'Manisha', 'assigned_area': 'Region B'},
            {'username': 'hashan', 'first_name': 'Hashan', 'assigned_area': 'Region C'},
            {'username': 'showroom', 'first_name': 'Showroom', 'assigned_area': 'Showroom HQ'},
            {'username': 'website', 'first_name': 'Website', 'assigned_area': 'Online/Digital'},
        ]

        created_count = 0
        for data in officers:
            if not User.objects.filter(username=data['username']).exists():
                user = User.objects.create_user(
                    username=data['username'],
                    password='password123', # Default password for testing
                    first_name=data['first_name'],
                    role=User.Roles.SALES_OFFICER,
                    assigned_area=data['assigned_area'],
                    is_staff=True # Needed for them to access their specific tools easily if leveraging admin proxy
                )
                self.stdout.write(self.style.SUCCESS(f"Successfully created Sales Officer: {user.username} (Password: password123)"))
                created_count += 1
            else:
                self.stdout.write(self.style.WARNING(f"Sales Officer {data['username']} already exists."))

        self.stdout.write(self.style.SUCCESS(f"Successfully seeded {created_count} Sales Officers."))
