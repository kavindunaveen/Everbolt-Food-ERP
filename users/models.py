from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    class Roles(models.TextChoices):
        ADMIN = 'ADMIN', 'Admin'
        SALES_OFFICER = 'SALES_OFFICER', 'Sales Officer'

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
