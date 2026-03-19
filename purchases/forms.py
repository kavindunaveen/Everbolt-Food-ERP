from django import forms
from django.forms import inlineformset_factory
from .models import GRN, GRNItem

class GRNForm(forms.ModelForm):
    class Meta:
        model = GRN
        fields = ['supplier', 'date', 'ref_number', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'supplier': forms.TextInput(attrs={'class': 'form-control'}),
            'ref_number': forms.TextInput(attrs={'class': 'form-control'}),
            'remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

class GRNItemForm(forms.ModelForm):
    class Meta:
        model = GRNItem
        fields = ['product', 'qty', 'unit_cost', 'batch', 'expiry']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-control'}),
            'qty': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.001'}),
            'unit_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'batch': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        }

GRNItemFormSet = inlineformset_factory(
    GRN, GRNItem, form=GRNItemForm,
    extra=1, can_delete=True
)
