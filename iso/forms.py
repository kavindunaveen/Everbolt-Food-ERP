from django import forms
from .models import ISOCategory, ISOCriteria, ISODailyPlan, ISODailyTask

class ISOCriteriaForm(forms.ModelForm):
    # This field handles adding a new category on the fly if needed
    new_category_name = forms.CharField(max_length=255, required=False, label="Or create a New Category")

    class Meta:
        model = ISOCriteria
        fields = ['name', 'category', 'duration_type', 'custom_duration_days']
        widgets = {
            'duration_type': forms.Select(attrs={'class': 'w-full'}),
            'category': forms.Select(attrs={'class': 'w-full'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].required = False # Because we can create a new one

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        new_category_name = cleaned_data.get('new_category_name')

        if not category and not new_category_name:
            raise forms.ValidationError("You must either select an existing category or provide a new category name.")
        
        duration_type = cleaned_data.get('duration_type')
        custom_duration = cleaned_data.get('custom_duration_days')
        
        if duration_type == ISOCriteria.DurationType.CUSTOM and not custom_duration:
            raise forms.ValidationError({'custom_duration_days': "Custom duration days is required if duration type is Custom."})

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        new_category_name = self.cleaned_data.get('new_category_name')
        
        if not instance.category_id and new_category_name:
            category, created = ISOCategory.objects.get_or_create(name=new_category_name)
            instance.category = category
            
        if commit:
            instance.save()
        return instance

class ISODailyPlanForm(forms.ModelForm):
    class Meta:
        model = ISODailyPlan
        fields = ['date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }
