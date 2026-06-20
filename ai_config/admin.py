from django.contrib import admin
from .models import AIModelConfiguration

@admin.register(AIModelConfiguration)
class AIModelConfigurationAdmin(admin.ModelAdmin):
    list_display = ('provider_name', 'model_name', 'is_active', 'updated_at', 'updated_by')
    list_filter = ('provider_name', 'is_active')
