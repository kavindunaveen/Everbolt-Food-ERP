import re
from django import forms
from django.core.exceptions import ValidationError
from .models import Customer

class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        exclude = ['customer_code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not getattr(field.widget, 'input_type', '') == 'checkbox':
                field.widget.attrs['class'] = 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm'
        
        # Filter assigned_sales_officer to show only SALES_OFFICER role
        if 'assigned_sales_officer' in self.fields:
            from users.models import User
            self.fields['assigned_sales_officer'].queryset = User.objects.filter(role=User.Roles.SALES_OFFICER)
            self.fields['assigned_sales_officer'].empty_label = "--- Select Sales Officer ---"
        
        # Enforce exact numeric entry on the frontend for Phone
        for field_name in ['phone', 'phone_secondary']:
            if field_name in self.fields:
                self.fields[field_name].widget.attrs.update({
                    'pattern': '[0-9]{10}',
                    'title': '10 digit numeric phone number',
                    'oninput': "this.value = this.value.replace(/[^0-9]/g, '').slice(0, 10);"
                })

    def _clean_phone_field(self, field_name):
        phone = self.cleaned_data.get(field_name, '')
        if not phone:
            return phone
        phone = re.sub(r'[^0-9]', '', phone)
        if len(phone) != 10:
            raise ValidationError(f"{field_name.replace('_', ' ').capitalize()} number must contain exactly 10 digits.")
        return phone

    def clean_phone(self):
        return self._clean_phone_field('phone')

    def clean_phone_secondary(self):
        return self._clean_phone_field('phone_secondary')
