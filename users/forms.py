from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from .models import User

def get_custom_permissions():
    """Returns permissions only for our custom apps."""
    return Permission.objects.filter(content_type__app_label__in=[
        'crm', 'inventory', 'sales', 'purchases', 'suppliers', 'users', 'manufacturing'
    ]).exclude(codename__icontains='logentry').exclude(codename__icontains='session')

class MatrixPermissionMixin:
    def get_permission_matrix(self):
        matrix = {}
        user_perms_ids = []
        if self.instance and self.instance.pk:
            user_perms_ids = list(self.instance.user_permissions.values_list('pk', flat=True))
            
        perms = get_custom_permissions().select_related('content_type')
        
        # Define the columns we care about
        actions = ['view', 'add', 'change', 'delete', 'approve']
        
        for perm in perms:
            # Model name formatted nicely
            model_name = perm.content_type.name.title()
            # Replace some names to match the 9 modules
            if model_name == 'User': model_name = 'Users'
            elif model_name == 'Customer': model_name = 'Contacts (Customers)'
            elif model_name == 'Supplier': model_name = 'Contacts (Suppliers)'
            elif model_name == 'Product': model_name = 'Products'
            elif model_name == 'Purchaseorder': model_name = 'Purchase Orders'
            elif model_name == 'Grn': model_name = 'GRN'
            elif model_name == 'Stockledger': model_name = 'Reports (Stock Ledger)'
            elif model_name == 'Productionorder': model_name = 'Manufacturing (Production Orders)'
            elif model_name == 'Bom': model_name = 'Manufacturing (BOM)'
            elif model_name == 'Bom Item': model_name = 'Manufacturing (BOM Items)'
            
            if model_name not in matrix:
                matrix[model_name] = {action: None for action in actions}
                matrix[model_name]['model'] = model_name
                
            action = perm.codename.split('_')[0]
            if action in actions:
                matrix[model_name][action] = {
                    'pk': perm.pk,
                    'checked': perm.pk in user_perms_ids or (self.instance and self.instance.pk and self.instance.is_admin())
                }
                
        rows = []
        for model_name, actions_dict in matrix.items():
            if any(actions_dict[a] for a in actions):
                cols = [actions_dict.get(a) for a in actions]
                rows.append({
                    'model': model_name,
                    'cols': cols
                })
        rows.sort(key=lambda x: x['model'])
        return rows

class CustomUserCreationForm(UserCreationForm, MatrixPermissionMixin):
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'user_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_permissions'].queryset = get_custom_permissions()

class CustomUserChangeForm(UserChangeForm, MatrixPermissionMixin):
    password = None
    new_password = forms.CharField(
        required=False, 
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter new password to reset'}), 
        label="Reset Password",
        help_text="Leave blank to keep the current password."
    )
    
    user_permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_active', 'user_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_permissions'].queryset = get_custom_permissions()

    def save(self, commit=True):
        user = super().save(commit=False)
        new_pass = self.cleaned_data.get('new_password')
        if new_pass:
            user.set_password(new_pass)
        if commit:
            user.save()
            self.save_m2m()
        return user
