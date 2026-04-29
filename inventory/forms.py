from django import forms
from .models import Product, StockAdjustment

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        # IMPORTANT: current_stock is EXCLUDED — it is a cached field maintained
        # exclusively by the StockLedger service. Editing it directly via this form
        # would corrupt the stock balance. Use Stock Adjustments to change stock levels.
        fields = [
            'product_id', 'name', 'brand', 'category', 'tea_type',
            'packet_size', 'stock_unit', 'selling_unit',
            'inventory_class', 'product_type',
            'track_stock', 'allow_negative_stock', 'reorder_level',
            'selling_price', 'price_tier_100', 'price_tier_250', 'price_tier_500',
            'custom_load_price', 'tax_rate',
            'status',
        ]
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
