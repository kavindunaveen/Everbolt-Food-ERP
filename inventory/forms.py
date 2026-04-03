from django import forms
from .models import Product, StockAdjustment

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'
        widgets = {
            'product_id': forms.TextInput(attrs={'readonly': 'readonly'})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not getattr(field.widget, 'input_type', '') == 'checkbox':
                base_class = 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
                if field_name == 'product_id':
                    field.widget.attrs['class'] = base_class + ' bg-gray-100 text-gray-500 hover:cursor-not-allowed'
                else:
                    field.widget.attrs['class'] = base_class

class StockAdjustmentForm(forms.ModelForm):
    class Meta:
        model = StockAdjustment
        fields = ['date', 'product', 'adjustment_type', 'quantity', 'reason', 'remarks']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'remarks': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if not getattr(field.widget, 'input_type', '') == 'checkbox':
                field.widget.attrs['class'] = 'w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 sm:text-sm'
