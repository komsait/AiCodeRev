import uuid
from django.db import models
from django.conf import settings

class Repository(models.Model):
    repository_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    repo_name = models.CharField(max_length=255)
    upload_type = models.CharField(max_length=50, default='manual')
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='repositories')

    class Meta:
        unique_together = ('user', 'repo_name')

    def __str__(self):
        return f"{self.user.username}/{self.repo_name}"
