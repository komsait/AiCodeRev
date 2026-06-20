from django.contrib import admin
from .models import Repository

@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ('repo_name', 'user', 'upload_type', 'created_at')
    search_fields = ('repo_name',)
    list_filter = ('upload_type', 'created_at')
