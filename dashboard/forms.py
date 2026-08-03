from django import forms
from .models import CompanySettings

class CompanySettingsForm(forms.ModelForm):
    SEQUENCE_CHOICES = [
        ('auto', 'Start with current increment (Auto)'),
        ('reset', 'Start from 00001 (Reset)'),
    ]
    sequence_behavior = forms.ChoiceField(
        choices=SEQUENCE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'h-4 w-4 text-emerald-600 focus:ring-emerald-500 border-gray-300'}),
        initial='auto',
        required=False
    )

    class Meta:
        model = CompanySettings
        fields = [
            'company_name', 'company_address', 'telephone_number',
            'email_address', 'website_url', 'tin_number', 'logo',
            'bank_account_name', 'bank_name', 'bank_account_number', 'bank_branch',
            'invoice_payment_modes', 'return_policy_days',
            'invoice_terms_and_conditions', 'quotation_terms_and_conditions',
            'invoice_number_format'
        ]
        _input = 'w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-emerald-500 focus:border-emerald-500'
        _textarea = 'w-full px-3 py-2 border border-gray-300 rounded-md text-sm focus:ring-emerald-500 focus:border-emerald-500'
        widgets = {
            'company_name': forms.TextInput(attrs={'class': _input}),
            'company_address': forms.Textarea(attrs={'class': _textarea, 'rows': 3}),
            'telephone_number': forms.TextInput(attrs={'class': _input}),
            'email_address': forms.EmailInput(attrs={'class': _input, 'placeholder': 'info@yourcompany.com'}),
            'website_url': forms.URLInput(attrs={'class': _input, 'placeholder': 'https://www.yourcompany.com'}),
            'tin_number': forms.TextInput(attrs={'class': _input}),
            'logo': forms.FileInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md bg-white text-sm'}),
            'bank_account_name': forms.TextInput(attrs={'class': _input}),
            'bank_name': forms.TextInput(attrs={'class': _input}),
            'bank_account_number': forms.TextInput(attrs={'class': _input}),
            'bank_branch': forms.TextInput(attrs={'class': _input}),
            'invoice_payment_modes': forms.TextInput(attrs={'class': _input}),
            'return_policy_days': forms.NumberInput(attrs={'class': _input, 'min': 1}),
            'invoice_terms_and_conditions': forms.Textarea(attrs={'class': _textarea, 'rows': 6, 'placeholder': 'Each line will appear as a separate line on the printed invoice...'}),
            'quotation_terms_and_conditions': forms.Textarea(attrs={'class': _textarea, 'rows': 6, 'placeholder': 'Each line will appear as a separate line on the printed quotation...'}),
            'invoice_number_format': forms.TextInput(attrs={'class': _input, 'placeholder': '{YY}{MMM}_EBFR_{SEQ}'}),
        }
