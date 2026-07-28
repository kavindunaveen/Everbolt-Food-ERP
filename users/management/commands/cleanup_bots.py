from django.core.management.base import BaseCommand
from users.models import User
import re

class Command(BaseCommand):
    help = 'Cleans up suspected bot users that registered through the public website.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING("Finding suspected bot users..."))
        
        bot_users = []
        # Only target users with the Website Customer role
        users = User.objects.filter(role__name="Website Customer")
        
        for user in users:
            # Check for suspicious patterns: extremely long first or last names with no spaces
            if (user.first_name and len(user.first_name) > 20 and ' ' not in user.first_name) or \
               (user.last_name and len(user.last_name) > 20 and ' ' not in user.last_name):
                bot_users.append(user)
        
        if not bot_users:
            self.stdout.write(self.style.SUCCESS("No bot users found."))
            return

        self.stdout.write(self.style.WARNING(f"Found {len(bot_users)} suspected bot users. Deleting them now..."))
        
        deleted_count = 0
        for user in bot_users:
            try:
                self.stdout.write(f"Deleting user: {user.username} (Name: {user.first_name} {user.last_name})")
                user.delete()
                deleted_count += 1
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Failed to delete {user.username}: {str(e)}"))
                
        self.stdout.write(self.style.SUCCESS(f"\nSuccessfully deleted {deleted_count} bot accounts."))
