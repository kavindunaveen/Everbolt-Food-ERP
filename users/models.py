from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        SALES_OFFICER = 'SALES_OFFICER', 'Sales Officer'
        USER = 'USER', 'User'

    role = models.CharField(max_length=50, choices=Roles.choices, default=Roles.SALES_OFFICER)
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    assigned_area = models.CharField(max_length=100, blank=True, null=True)
    
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser
        
    def is_sales_officer(self):
        return self.role == self.Roles.SALES_OFFICER

    # Prevent normal sales officers from accessing the main Django Admin completely
    # They should use our custom dashboard frontend instead.
    @property
    def is_staff(self):
        if self.is_admin():
            return True
        return False

    @property
    def unread_notifications(self):
        # We handle notifications from the related name 'notifications'
        return getattr(self, 'notifications', None) and self.notifications.filter(is_read=False).order_by('-created_at') or []

    def has_perm(self, perm, obj=None):
        if self.is_admin():
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if self.is_admin():
            return True
        return super().has_module_perms(app_label)

    def __str__(self):
        return f"{self.username} - {self.get_role_display()}"


class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.recipient.username}: {self.title}"

class SavedFilter(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_filters')
    model_name = models.CharField(max_length=50) # e.g. Customer, Invoice, Quotation
    name = models.CharField(max_length=255)
    query_string = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username}'s filter: {self.name} on {self.model_name}"
