from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from ai_config.models import AIModelConfiguration
from analysis.providers.factory import AIProviderFactory
from analysis.providers.gemini import GeminiProvider
import os
from unittest.mock import patch

User = get_user_model()

class AIConfigTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.admin_user = User.objects.create_user(username='admin', password='password', is_staff=True)
        self.normal_user = User.objects.create_user(username='user', password='password', is_staff=False)
        self.url = reverse('admin-dashboard')
        
    def test_admin_redirect_after_login(self):
        response = self.client.post(reverse('login'), {'username': 'admin', 'password': 'password'})
        self.assertRedirects(response, self.url)
        
    def test_normal_user_redirect_after_login(self):
        response = self.client.post(reverse('login'), {'username': 'user', 'password': 'password'})
        self.assertRedirects(response, reverse('dashboard'))
        
    def test_admin_only_access_to_ai_settings(self):
        self.client.login(username='user', password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)
        
        self.client.login(username='admin', password='password')
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        
    def test_save_active_provider_configuration(self):
        self.client.login(username='admin', password='password')
        response = self.client.post(self.url, {
            'provider_name': 'openai',
            'model_name': 'gpt-4o'
        })
        self.assertRedirects(response, self.url)
        
        config = AIModelConfiguration.objects.first()
        self.assertIsNotNone(config)
        self.assertEqual(config.provider_name, 'openai')
        self.assertEqual(config.model_name, 'gpt-4o')
        self.assertTrue(config.is_active)
        
    def test_only_one_provider_active(self):
        config1 = AIModelConfiguration.objects.create(
            provider_name='openai', model_name='gpt-4o', is_active=True
        )
        config1.save()
        
        config2 = AIModelConfiguration.objects.create(
            provider_name='gemini', model_name='gemini-2.5-flash', is_active=True
        )
        config2.save()
        
        config1.refresh_from_db()
        config2.refresh_from_db()
        
        self.assertFalse(config1.is_active)
        self.assertTrue(config2.is_active)
        
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'env-key'})
    def test_provider_factory_returns_configured(self):
        config = AIModelConfiguration.objects.create(
            provider_name='gemini', model_name='gemini-pro', is_active=True
        )
        config.save()
        
        provider = AIProviderFactory.get_provider()
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.model_name, 'gemini-pro')
        
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'env-key'})
    @patch.dict(os.environ, {'GEMINI_API_KEY': 'env-key'})
    def test_provider_factory_fallback(self):
        AIModelConfiguration.objects.all().delete()
        
        provider = AIProviderFactory.get_provider()
        self.assertIsInstance(provider, GeminiProvider)
        self.assertEqual(provider.api_key, 'env-key')
