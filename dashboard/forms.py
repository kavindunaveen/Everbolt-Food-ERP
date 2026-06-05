from django import forms
from .models import CompanySettings

class CompanySettingsForm(forms.ModelForm):
    class Meta:
        model = CompanySettings
        fields = ['company_name', 'company_address', 'telephone_number', 'tin_number', 'logo']
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'company_address': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
            'telephone_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'tin_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'logo': forms.FileInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md bg-white'}),
        }
