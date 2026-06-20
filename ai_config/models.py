import uuid
from django.db import models
from django.conf import settings
from cryptography.fernet import Fernet
import base64
import hashlib

class AIModelConfiguration(models.Model):
    PROVIDER_CHOICES = [
        ('openai', 'OpenAI'),
        ('gemini', 'Google Gemini'),
        ('claude', 'Anthropic Claude'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider_name = models.CharField(max_length=20, choices=PROVIDER_CHOICES)
    model_name = models.CharField(max_length=100)
    api_key = models.TextField()
    is_active = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.get_provider_name_display()} ({self.model_name})"

    def save(self, *args, **kwargs):
        if self.is_active:
            # Deactivate all other configurations
            AIModelConfiguration.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        super().save(*args, **kwargs)

    def _get_cipher(self):
        # Use SECRET_KEY to derive a valid 32-url-safe-base64-encoded key for Fernet
        key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
        fernet_key = base64.urlsafe_b64encode(key)
        return Fernet(fernet_key)

    def set_api_key(self, raw_key):
        if raw_key:
            cipher = self._get_cipher()
            self.api_key = cipher.encrypt(raw_key.encode()).decode()

    def get_api_key(self):
        if self.api_key:
            try:
                cipher = self._get_cipher()
                return cipher.decrypt(self.api_key.encode()).decode()
            except Exception:
                return None
        return None

    def get_masked_key(self):
        key = self.get_api_key()
        if not key:
            return ""
        if len(key) <= 8:
            return "sk-****"
        return f"sk-...{key[-4:]}"
