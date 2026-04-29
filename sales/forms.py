from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, QuotationItem, Invoice, InvoiceItem

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['customer', 'valid_until', 'customer_po_number', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer_po_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
        }

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['product', 'quantity', 'unit_price', 'discount']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md font-medium text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-center font-bold text-sm min-w-[80px]', 'step': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm min-w-[100px]', 'step': '0.01'}),
            'discount': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm min-w-[100px]', 'step': '0.01'}),
        }

QuotationItemFormSet = inlineformset_factory(
    Quotation, QuotationItem, form=QuotationItemForm,
    extra=1, can_delete=True
)

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'invoice_type', 'delivery_date', 'due_date', 'customer_po_number', 'notes']
        widgets = {
            'customer': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'invoice_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer_po_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
        }

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'quantity', 'unit_price', 'discount']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md font-medium text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-center font-bold text-sm min-w-[80px]'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm min-w-[100px] step-any'}),
            'discount': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm min-w-[100px] step-any'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        quantity = cleaned_data.get('quantity')
        
        if product and quantity:
            if quantity > product.current_stock:
                self.add_error('quantity', f"Only {product.current_stock} currently in stock.")
        return cleaned_data

InvoiceItemFormSet = inlineformset_factory(
    Invoice, InvoiceItem, form=InvoiceItemForm,
    extra=1, can_delete=True
)
