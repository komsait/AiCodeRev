import uuid
from django.db import models
from analysis.models import CodeSmell

class RefactoringSuggestion(models.Model):
    suggestion_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    suggestion_text = models.TextField()
    status = models.CharField(max_length=20, default='Pending') # Pending, Accepted, Rejected
    smell = models.ForeignKey(CodeSmell, on_delete=models.CASCADE, related_name='suggestions')

    # Editable refactoring fields
    developer_edited_code = models.TextField(blank=True, null=True)
    was_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(blank=True, null=True)
    accepted_at = models.DateTimeField(blank=True, null=True)
    applied_code = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Suggestion for {self.smell.smell_type}"

