from django import forms
from django.forms import inlineformset_factory
from .models import BOM, BOMItem, Production, ProductionMaterial, ProductionOutput

class BOMForm(forms.ModelForm):
    class Meta:
        model = BOM
        fields = ['finished_product', 'version', 'is_active', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'finished_product' in self.fields:
            self.fields['finished_product'].queryset = self.fields['finished_product'].queryset.filter(status=True)

class BOMItemForm(forms.ModelForm):
    class Meta:
        model = BOMItem
        fields = ['component_product', 'qty_required']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'component_product' in self.fields:
            self.fields['component_product'].queryset = self.fields['component_product'].queryset.filter(status=True)

BOMItemFormSet = inlineformset_factory(
    BOM, BOMItem, form=BOMItemForm,
    extra=1, can_delete=True
)

class ProductionForm(forms.ModelForm):
    # Field to select finished product to load BOM
    finished_product_select = forms.ModelChoiceField(
        queryset=BOM.objects.filter(is_active=True), 
        required=False, 
        label="Load from Active BOM",
        help_text="Selecting this will pre-fill materials"
    )

    class Meta:
        model = Production
        fields = ['date', 'conversion_type', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

class ProductionMaterialForm(forms.ModelForm):
    class Meta:
        model = ProductionMaterial
        fields = ['component_product', 'required_qty', 'actual_used_qty', 'wastage_qty']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'component_product' in self.fields:
            self.fields['component_product'].queryset = self.fields['component_product'].queryset.filter(status=True)

ProductionMaterialFormSet = inlineformset_factory(
    Production, ProductionMaterial, form=ProductionMaterialForm,
    extra=1, can_delete=True
)

class ProductionOutputForm(forms.ModelForm):
    class Meta:
        model = ProductionOutput
        fields = ['output_product', 'produced_qty']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'output_product' in self.fields:
            self.fields['output_product'].queryset = self.fields['output_product'].queryset.filter(status=True)

ProductionOutputFormSet = inlineformset_factory(
    Production, ProductionOutput, form=ProductionOutputForm,
    extra=1, can_delete=True
)
