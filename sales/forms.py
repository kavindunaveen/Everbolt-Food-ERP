from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, QuotationItem, Invoice, InvoiceItem, DeliveryNote, DeliveryNoteItem

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['customer', 'valid_until', 'customer_po_number', 'custom_discount_type', 'custom_discount_value', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer_po_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'custom_discount_type': forms.HiddenInput(),
            'custom_discount_value': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
        }

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['product', 'quantity', 'unit_price', 'discount_type', 'discount']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md font-medium text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-center font-bold text-sm hide-arrows', 'step': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows', 'step': '0.01'}),
            'discount_type': forms.HiddenInput(),
            'discount': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows', 'step': '0.01'}),
        }

QuotationItemFormSet = inlineformset_factory(
    Quotation, QuotationItem, form=QuotationItemForm,
    extra=1, can_delete=True
)

class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['customer', 'invoice_type', 'delivery_date', 'due_date', 'customer_po_number', 'custom_discount_type', 'custom_discount_value', 'notes']
        widgets = {
            'customer': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'invoice_type': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer_po_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'custom_discount_type': forms.HiddenInput(),
            'custom_discount_value': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
        }

class InvoiceItemForm(forms.ModelForm):
    class Meta:
        model = InvoiceItem
        fields = ['product', 'quantity', 'unit_price', 'discount_type', 'discount']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md font-medium text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-center font-bold text-sm hide-arrows'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows step-any'}),
            'discount_type': forms.HiddenInput(),
            'discount': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows', 'step': '0.01'}),
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

class DeliveryNoteForm(forms.ModelForm):
    class Meta:
        model = DeliveryNote
        fields = ['invoice', 'customer_name', 'delivery_address', 'delivery_date', 'delivered_by', 'other_delivery_person', 'remarks']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'w-full select2-ajax-invoice'}),
            'customer_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'readonly': 'readonly'}),
            'delivery_address': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'rows': 2, 'readonly': 'readonly'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'readonly': 'readonly'}),
            'delivered_by': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-md'}),
            'other_delivery_person': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'placeholder': 'Enter name if Other'}),
            'remarks': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['invoice'].queryset = Invoice.objects.filter(status='ISSUED')
