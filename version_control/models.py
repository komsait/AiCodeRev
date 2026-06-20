import uuid
from django.db import models
from repository.models import Repository

class Commit(models.Model):
    commit_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    commit_hash = models.CharField(max_length=40)
    commit_message = models.TextField()
    commit_date = models.DateTimeField(auto_now_add=True)
    repository = models.ForeignKey(Repository, on_delete=models.CASCADE, related_name='system_commits')

    def __str__(self):
        return self.commit_hash[:7]
