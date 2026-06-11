from django.contrib.auth.models import AbstractUser, Permission
from django.db import models

class Role(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    permissions = models.ManyToManyField(Permission, blank=True)
    is_system = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    
    contact_number = models.CharField(max_length=20, blank=True, null=True)
    assigned_area = models.CharField(max_length=100, blank=True, null=True)
    is_delivery_officer = models.BooleanField(default=False, verbose_name="Is a Delivery Officer?", help_text="User can be assigned to deliver orders.")
    monthly_target = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, help_text="Monthly sales target (Ex-VAT) for this officer.")
    can_set_targets = models.BooleanField(default=False, verbose_name="Can Set Sales Targets?", help_text="Allow this user to access the Analytics Target Management page.")
    can_view_all_sales_performance = models.BooleanField(default=False, verbose_name="Can View All Sales Performance?", help_text="Allow this user to view other sales officers' performance in the analytics dashboard.")
    receive_email_alerts = models.BooleanField(default=True, verbose_name="Receive Email Alerts", help_text="Receive email notifications for approvals and alerts.")
    
    def is_admin(self):
        if self.role:
            return self.is_superuser or (self.role.name == 'Administrator' and self.role.is_system)
        return self.is_superuser
        
    def is_sales_officer(self):
        if self.role:
            return self.role.name == 'Sales Officer'
        return False

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
        if self.role:
            if self.role.name == 'Administrator':
                self.is_superuser = True
                self.is_staff = True
            elif self.username != 'admin':
                self.is_superuser = False
                self.is_staff = False
        super().save(*args, **kwargs)

    def __str__(self):
        if self.role:
            return f"{self.username} - {self.role.name}"
        return f"{self.username} - No Role"


class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('approval_required', 'Approval Required'),
    )
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=255)
    message = models.TextField()
    link = models.CharField(max_length=255, blank=True, null=True)
    action_approve_url = models.CharField(max_length=255, blank=True, null=True)
    action_reject_url = models.CharField(max_length=255, blank=True, null=True)
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
