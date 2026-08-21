from django import forms
from django.forms import inlineformset_factory
from .models import Quotation, QuotationItem, Invoice, InvoiceItem, DeliveryNote, DeliveryNoteItem, Return, ReturnItem

class QuotationForm(forms.ModelForm):
    class Meta:
        model = Quotation
        fields = ['customer', 'valid_until', 'custom_discount_type', 'custom_discount_value', 'notes']
        widgets = {
            'valid_until': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'customer': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md'}),
            'custom_discount_type': forms.HiddenInput(),
            'custom_discount_value': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-right font-bold text-sm', 'step': '0.01'}),
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 3}),
        }

class QuotationItemForm(forms.ModelForm):
    class Meta:
        model = QuotationItem
        fields = ['product', 'custom_product_name', 'quantity', 'unit_price', 'discount_type', 'discount']
        widgets = {
            'custom_product_name': forms.HiddenInput(),
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md font-medium text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-center font-bold text-sm hide-arrows', 'step': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows', 'step': '0.01'}),
            'discount_type': forms.HiddenInput(),
            'discount': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right font-bold text-sm hide-arrows', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.fields:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(status=True)

    def clean(self):
        cleaned_data = super().clean()
        product = cleaned_data.get('product')
        custom_product_name = cleaned_data.get('custom_product_name')
        
        if not product and not custom_product_name and not self.cleaned_data.get('DELETE'):
            raise forms.ValidationError("You must select a product or enter a custom product name.")
        
        return cleaned_data

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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.fields:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(status=True)

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
        fields = ['invoice', 'customer_name', 'delivery_address', 'delivery_date', 'delivered_by', 'remarks']
        widgets = {
            'invoice': forms.Select(attrs={'class': 'w-full select2-ajax-invoice'}),
            'customer_name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'readonly': 'readonly'}),
            'delivery_address': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'rows': 2, 'readonly': 'readonly'}),
            'delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 border rounded-md bg-gray-50', 'readonly': 'readonly'}),
            'delivered_by': forms.Select(attrs={'class': 'w-full px-3 py-2 border rounded-md'}),
            'remarks': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            from django.db.models import Q
            self.fields['invoice'].queryset = Invoice.objects.filter(
                Q(status__in=['ISSUED', 'PAID'], delivery_notes__isnull=True) | Q(pk=self.instance.invoice.pk)
            ).distinct()
        else:
            self.fields['invoice'].queryset = Invoice.objects.filter(status__in=['ISSUED', 'PAID'], delivery_notes__isnull=True)
        
        # Delivery fields might be empty if the customer lacks an address, or JS hasn't filled them.
        self.fields['customer_name'].required = False
        self.fields['delivery_address'].required = False
        self.fields['delivery_date'].required = False
        
        from users.models import User
        if self.instance and self.instance.pk:
            self.fields['invoice'].widget.attrs['disabled'] = True
            self.fields['invoice'].required = False
        if 'delivered_by' in self.fields:
            self.fields['delivered_by'].queryset = User.objects.filter(is_active=True, is_delivery_officer=True)
            self.fields['delivered_by'].empty_label = "--- Select Delivery Officer ---"

    def clean_invoice(self):
        if self.instance and self.instance.pk:
            return self.instance.invoice
        return self.cleaned_data.get('invoice')

class ReturnForm(forms.ModelForm):
    class Meta:
        model = Return
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md', 'rows': 2}),
        }

class ReturnItemForm(forms.ModelForm):
    class Meta:
        model = ReturnItem
        fields = ['product', 'quantity', 'unit_price', 'reason', 'condition']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-3 py-2 border border-gray-300 rounded-md text-sm product-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-center text-sm', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-right text-sm step-any', 'readonly': 'readonly'}),
            'reason': forms.Select(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-sm'}),
            'condition': forms.Select(attrs={'class': 'w-full px-2 py-2 border border-gray-300 rounded-md text-sm'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.fields:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(status=True)

ReturnItemFormSet = inlineformset_factory(
    Return, ReturnItem, form=ReturnItemForm,
    extra=1, can_delete=True
)

from .models import CreditNote, CreditNoteItem

class CreditNoteForm(forms.ModelForm):
    class Meta:
        model = CreditNote
        fields = ['notes']
        widgets = {
            'notes': forms.Textarea(attrs={'class': 'w-full px-3 py-2 border rounded-md', 'rows': 3}),
        }

class CreditNoteItemForm(forms.ModelForm):
    class Meta:
        model = CreditNoteItem
        fields = ['product', 'quantity', 'unit_price', 'credit_amount']
        widgets = {
            'product': forms.Select(attrs={'class': 'w-full px-2 py-2 border rounded-md text-sm'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border rounded-md text-sm', 'min': '1'}),
            'unit_price': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border rounded-md text-sm', 'step': '0.01'}),
            'credit_amount': forms.NumberInput(attrs={'class': 'w-full px-2 py-2 border rounded-md text-sm', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'product' in self.fields:
            self.fields['product'].queryset = self.fields['product'].queryset.filter(status=True)

CreditNoteItemFormSet = inlineformset_factory(
    CreditNote, CreditNoteItem, form=CreditNoteItemForm,
    extra=1, can_delete=True
)

