from django import forms
from .models import AIModelConfiguration

class AIConfigForm(forms.ModelForm):
    class Meta:
        model = AIModelConfiguration
        fields = ['provider_name', 'model_name']
        widgets = {
            'provider_name': forms.Select(attrs={'class': 'form-select'}),
            'model_name': forms.TextInput(attrs={'class': 'form-input'}),
        }
