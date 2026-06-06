from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import User, Role

# The curated list of permission rows the admin should see
PERMISSION_MODULES = [
    # (Display Name, app_label, model_name, actions)
    ("Customers",           "crm",           "customer",        ["view", "add", "change", "delete"]),
    ("Suppliers",           "suppliers",     "supplier",        ["view", "add", "change", "delete"]),
    ("Quotations",          "sales",         "quotation",       ["view", "add", "change", "delete"]),
    ("Invoices",            "sales",         "invoice",         ["view", "add", "change", "delete", "approve"]),
    ("Delivery Notes",      "sales",         "deliverynote",    ["view", "add", "change", "delete", "approve"]),
    ("Returns",             "sales",         "return",          ["view", "add", "change", "delete"]),
    ("Products",            "inventory",     "product",         ["view", "add", "change", "delete"]),
    ("Stock Adjustments",   "inventory",     "stockadjustment", ["view", "add", "change", "delete"]),
    ("Purchase Orders",     "purchases",     "purchaseorder",   ["view", "add", "change", "delete"]),
    ("GRN",                 "purchases",     "grn",             ["view", "add", "change", "delete"]),
    ("BOM",                 "manufacturing", "bom",             ["view", "add", "change", "delete"]),
    ("Production Orders",   "manufacturing", "production",      ["view", "add", "change", "delete"]),
    ("Users",               "users",         "user",            ["view", "add", "change", "delete"]),
]

class MatrixPermissionMixin:
    def get_permission_matrix(self):
        user_perms_ids = []
        if self.instance and self.instance.pk:
            # If it's a User instance
            if hasattr(self.instance, 'user_permissions'):
                user_perms_ids = list(self.instance.user_permissions.values_list('pk', flat=True))
                # Also get role permissions
                if self.instance.role:
                    user_perms_ids.extend(self.instance.role.permissions.values_list('pk', flat=True))
            # If it's a Role instance
            elif hasattr(self.instance, 'permissions'):
                user_perms_ids = list(self.instance.permissions.values_list('pk', flat=True))

        rows = []
        for display_name, app_label, model_name, actions in PERMISSION_MODULES:
            row = {
                'model': display_name,
                'cols': []
            }
            # For each action, find the exact permission
            for action in ['view', 'add', 'change', 'delete', 'approve']:
                if action in actions:
                    if action == 'approve' and model_name == 'deliverynote':
                        codename = "change_dn_status"
                    else:
                        codename = f"{action}_{model_name}"
                    
                    perm = Permission.objects.filter(content_type__app_label=app_label, codename=codename).first()
                    if perm:
                        checked = perm.pk in user_perms_ids
                        # If user is admin, everything is checked in UI
                        if hasattr(self.instance, 'is_admin') and self.instance.pk and self.instance.is_admin():
                            checked = True
                        
                        row['cols'].append({
                            'pk': perm.pk,
                            'checked': checked
                        })
                    else:
                        row['cols'].append(None)
                else:
                    row['cols'].append(None)
            rows.append(row)
        return rows


class CustomUserCreationForm(UserCreationForm, MatrixPermissionMixin):
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_delivery_officer', 'can_set_targets', 'user_permissions')


class CustomUserChangeForm(UserChangeForm, MatrixPermissionMixin):
    password = None
    new_password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password to reset'}), 
        label="Reset Password",
        help_text="Leave blank to keep the current password."
    )
    
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_delivery_officer', 'can_set_targets', 'is_active', 'user_permissions')

    def clean_role(self):
        role = self.cleaned_data.get('role')
        if self.instance and self.instance.pk and self.instance.is_superuser:
            if not role or role.name != 'Administrator':
                from .models import User
                admin_count = User.objects.filter(is_superuser=True, is_active=True).count()
                if admin_count <= 1:
                    from django.core.exceptions import ValidationError
                    raise ValidationError("Cannot change role. You are the last active Administrator in the system.")
        return role

    def save(self, commit=True):
        user = super().save(commit=False)
        new_pass = self.cleaned_data.get('new_password')
        if new_pass:
            user.set_password(new_pass)
        if commit:
            user.save()
            self.save_m2m()
        return user


class RoleForm(forms.ModelForm, MatrixPermissionMixin):
    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = Role
        fields = ('name', 'description', 'permissions')

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if self.instance and self.instance.is_system and self.instance.name != name:
            from django.core.exceptions import ValidationError
            raise ValidationError("You cannot rename a system role.")
        return name
