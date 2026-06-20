from django.contrib import admin
from .models import RefactoringSuggestion

@admin.register(RefactoringSuggestion)
class RefactoringSuggestionAdmin(admin.ModelAdmin):
    list_display = ('suggestion_id', 'smell', 'status')
    list_filter = ('status',)
