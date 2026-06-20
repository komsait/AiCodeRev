from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from repository.models import Repository

User = get_user_model()

class ExportTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='exporter', password='pw')
        self.client.login(username='exporter', password='pw')
        self.export_url = reverse('export')

    def test_export_no_repo(self):
        response = self.client.get(self.export_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'export.html')
        self.assertContains(response, 'Select a Repository to Export')
        
    def test_export_with_repo_view(self):
        repo = Repository.objects.create(user=self.user, repo_name='TestRepo')
        response = self.client.get(f"{self.export_url}?repo={repo.repository_id}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Ready to Download')
