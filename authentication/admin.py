from django.contrib import admin
from .models import User

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'created_at', 'is_active')
    search_fields = ('username', 'email')
    list_filter = ('is_active', 'created_at')
