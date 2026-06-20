from django.contrib import admin
from .models import Commit

@admin.register(Commit)
class CommitAdmin(admin.ModelAdmin):
    list_display = ('commit_hash', 'commit_message', 'repository', 'commit_date')
    search_fields = ('commit_hash', 'commit_message')
    list_filter = ('commit_date',)
