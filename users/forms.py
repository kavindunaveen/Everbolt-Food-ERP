from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth.models import Permission
from .models import User

def get_custom_permissions():
    """Returns permissions only for our custom apps."""
    return Permission.objects.filter(content_type__app_label__in=['crm', 'inventory', 'sales'])

class CustomPermissionChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        # Turns "Can add product" into "Add Product"
        return obj.name.replace('Can ', '').title()

class CustomUserCreationForm(UserCreationForm):
    user_permissions = CustomPermissionChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Access Rights"
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'user_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_permissions'].queryset = get_custom_permissions()

    def get_grouped_permissions(self):
        grouped = {}
        for perm in self.fields['user_permissions'].queryset.select_related('content_type'):
            app_label = perm.content_type.app_label.title()
            if app_label == 'Crm': app_label = 'CRM'
            
            if app_label not in grouped:
                grouped[app_label] = []
                
            grouped[app_label].append({
                'pk': perm.pk,
                'label': perm.name.replace('Can ', '').title(),
                'checked': False
            })
        return grouped

class CustomUserChangeForm(UserChangeForm):
    password = None
    
    user_permissions = CustomPermissionChoiceField(
        queryset=Permission.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Access Rights"
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'role', 'contact_number', 'assigned_area', 'is_active', 'user_permissions')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_permissions'].queryset = get_custom_permissions()

    def get_grouped_permissions(self):
        grouped = {}
        user_perms_ids = []
        if self.instance and self.instance.pk:
            user_perms_ids = list(self.instance.user_permissions.values_list('pk', flat=True))
            
        for perm in self.fields['user_permissions'].queryset.select_related('content_type'):
            app_label = perm.content_type.app_label.title()
            if app_label == 'Crm': app_label = 'CRM'
            
            if app_label not in grouped:
                grouped[app_label] = []
                
            grouped[app_label].append({
                'pk': perm.pk,
                'label': perm.name.replace('Can ', '').title(),
                'checked': perm.pk in user_perms_ids
            })
        return grouped
