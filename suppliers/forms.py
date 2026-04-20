from django import forms
from .models import Supplier, SupplierType

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = [
            'supplier_name', 'supplier_type', 'custom_supplier_type',
            'address_line1', 'address_line2', 'city', 'province', 'zip_code',
            'contact_number', 'email', 
            'bank_name', 'bank_branch', 'bank_account_no', 'vat_reg_num'
        ]
        widgets = {
            'supplier_name': forms.TextInput(attrs={'placeholder': 'Enter supplier name'}),
            'supplier_type': forms.Select(attrs={'class': 'select2-dropdown', 'data-placeholder': 'Search/Select type...'}),
            'custom_supplier_type': forms.TextInput(attrs={'placeholder': 'Enter custom type name'}),
            'address_line1': forms.TextInput(attrs={'placeholder': 'Street Address'}),
            'address_line2': forms.TextInput(attrs={'placeholder': 'Apartment, suite, etc. (optional)'}),
            'city': forms.TextInput(attrs={'placeholder': 'City / Town'}),
            'province': forms.Select(attrs={'class': 'select2-dropdown'}),
            'zip_code': forms.TextInput(attrs={'placeholder': 'Postal code'}),
            'contact_number': forms.NumberInput(attrs={'placeholder': 'Enter contact number (no letters)'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Enter valid email address'}),
            'bank_name': forms.Select(attrs={'class': 'select2-dropdown', 'data-placeholder': 'Select Commercial Bank...'}),
            'bank_branch': forms.Select(attrs={'class': 'select2-tags', 'data-placeholder': 'Type or select a branch...'}),
            'bank_account_no': forms.TextInput(attrs={'placeholder': 'Enter account number'}),
            'vat_reg_num': forms.TextInput(attrs={'placeholder': 'Enter VAT registration number'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Dynamically load existing unique bank branches for Select2
        # We append the current instance's branch if it's set to ensure it's selected properly
        existing_branches = Supplier.objects.exclude(bank_branch__isnull=True).exclude(bank_branch='').values_list('bank_branch', flat=True).distinct()
        branch_choices = [('', '---------')] + [(b, b) for b in existing_branches]
        if self.instance and self.instance.pk and self.instance.bank_branch and self.instance.bank_branch not in existing_branches:
            branch_choices.append((self.instance.bank_branch, self.instance.bank_branch))
            
        # Temporarily make the CharField act as a ChoiceField dynamically for Select2 tags
        # but disable Choice validation because Select2 'tags: true' allows custom inputs.
        # Actually, using a Select widget implies Choice validation if we use TypedChoiceField,
        # but here it's still a CharField. CharField with a Select widget validates that the 
        # posted value is in self.fields['bank_branch'].choices if we set it. Wait, Django CharField 
        # doesn't natively check choices unless it is a ChoiceField. But the Select widget requires choices.
        self.fields['bank_branch'].widget.choices = branch_choices

    def clean(self):
        cleaned_data = super().clean()
        supplier_type = cleaned_data.get("supplier_type")
        custom_supplier_type = cleaned_data.get("custom_supplier_type")

        if supplier_type == SupplierType.OTHER and not custom_supplier_type:
            self.add_error('custom_supplier_type', "You must provide a custom type when 'Other' is selected.")
        
        return cleaned_data
