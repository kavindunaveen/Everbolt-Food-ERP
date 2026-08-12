from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import User, Role

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

        target_apps = ['crm', 'suppliers', 'sales', 'inventory', 'manufacturing', 'purchases', 'users', 'dashboard', 'website', 'visits', 'finance', 'iso']
        from django.contrib.contenttypes.models import ContentType
        from django.contrib.auth.models import Permission

        content_types = ContentType.objects.filter(app_label__in=target_apps)
        all_perms = Permission.objects.filter(content_type__in=content_types).select_related('content_type')

        action_map = {}
        for p in all_perms:
            codename = p.codename
            model_name = p.content_type.model
            if codename.endswith(f"_{model_name}"):
                action = codename[:-(len(model_name) + 1)]
            else:
                action = codename
            action_map[p.pk] = action

        base_actions = ['view', 'add', 'change', 'delete']
        other_actions = list(set(action_map.values()) - set(base_actions))
        other_actions.sort()
        all_actions = base_actions + other_actions

        rows = []
        for ct in content_types:
            ct_perms = [p for p in all_perms if p.content_type == ct]
            if not ct_perms:
                continue

            display_name = ct.name.title()
            row = {
                'model': display_name,
                'cols': []
            }
            
            for action in all_actions:
                matching_perms = [p for p in ct_perms if action_map[p.pk] == action]
                if matching_perms:
                    perm = matching_perms[0]
                    checked = perm.pk in user_perms_ids
                    if hasattr(self.instance, 'is_admin') and getattr(self.instance, 'pk', None) and self.instance.is_admin():
                        checked = True
                    row['cols'].append({
                        'pk': perm.pk,
                        'name': perm.name,
                        'checked': checked
                    })
                else:
                    row['cols'].append(None)
                    
            rows.append(row)
            
        return {
            'headers': [a.replace('_', ' ').title() for a in all_actions],
            'rows': rows
        }


class CustomUserCreationForm(UserCreationForm, MatrixPermissionMixin):
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_delivery_officer', 'can_set_targets', 'can_view_all_sales_performance', 'user_permissions')


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
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_delivery_officer', 'can_set_targets', 'can_view_all_sales_performance', 'is_active', 'user_permissions')

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
