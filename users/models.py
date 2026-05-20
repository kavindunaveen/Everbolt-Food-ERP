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
    is_delivery_officer = models.BooleanField(default=False, verbose_name="Is a Delivery Officer?", help_text="User can be assigned to deliver orders.")
    monthly_target = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monthly sales target (Ex-VAT) for this officer.")
    can_set_targets = models.BooleanField(default=False, verbose_name="Can Set Sales Targets?", help_text="Allow this user to access the Analytics Target Management page.")
    
    def is_admin(self):
        return self.role == self.Roles.ADMIN or self.is_superuser
        
    def is_sales_officer(self):
        return self.role == self.Roles.SALES_OFFICER

    # Prevent normal sales officers from accessing the main Django Admin completely
    # They should use our custom dashboard frontend instead.

    @property
    def unread_notifications(self):
        # We handle notifications from the related name 'notifications'
        return getattr(self, 'notifications', None) and self.notifications.filter(is_read=False).order_by('-created_at') or []

    @property
    def recent_notifications(self):
        return getattr(self, 'notifications', None) and self.notifications.order_by('-created_at')[:20] or []

    def has_perm(self, perm, obj=None):
        if self.is_admin():
            return True
        return super().has_perm(perm, obj)

    def has_module_perms(self, app_label):
        if self.is_admin():
            return True
        return super().has_module_perms(app_label)

    def save(self, *args, **kwargs):
        if self.role == self.Roles.ADMIN:
            self.is_superuser = True
            self.is_staff = True
        else:
            # We don't want to demote the hardcoded superadmin 'admin'
            if self.username != 'admin':
                self.is_superuser = False
                self.is_staff = False
        super().save(*args, **kwargs)

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
