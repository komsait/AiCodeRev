import os
import shutil
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.conf import settings
from .models import Repository

User = get_user_model()

class RepositoryTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='repo_user', password='password')
        self.client.login(username='repo_user', password='password')
        self.repos_url = reverse('repositories')
        self.upload_url = reverse('upload')

    def tearDown(self):
        # Clean up created workspaces to prevent dangling files in test mode
        user_workspace = os.path.join(settings.MEDIA_ROOT, str(self.user.id))
        if os.path.exists(user_workspace):
            shutil.rmtree(user_workspace, ignore_errors=True)

    def test_initialize_repository(self):
        response = self.client.post(self.repos_url, {
            'repo_name': 'MyTestRepo',
            'upload_after': 'off'
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Repository.objects.filter(repo_name='MyTestRepo', user=self.user).exists())
        
        repo = Repository.objects.get(repo_name='MyTestRepo')
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(repo.repository_id))
        self.assertTrue(os.path.exists(repo_path))
        self.assertTrue(os.path.exists(os.path.join(repo_path, '.git')))

    def test_duplicate_repository_name(self):
        Repository.objects.create(user=self.user, repo_name='DuplicateRepo')
        response = self.client.post(self.repos_url, {
            'repo_name': 'DuplicateRepo'
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn('error', response.json())

    def test_upload_supported_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        import git
        repo = Repository.objects.create(user=self.user, repo_name='UploadRepo')
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(repo.repository_id))
        os.makedirs(repo_path, exist_ok=True)
        git.Repo.init(repo_path)
        
        file = SimpleUploadedFile("test.py", b"print('hello')")
        response = self.client.post(self.upload_url, {'repo_id': repo.repository_id, 'files': [file]})
        self.assertEqual(response.status_code, 200)
        self.assertIn('test.py', response.json().get('tree', []))
        self.assertTrue(os.path.exists(os.path.join(repo_path, 'test.py')))
        
    def test_upload_unsupported_file(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        import git
        repo = Repository.objects.create(user=self.user, repo_name='UploadRepo2')
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(repo.repository_id))
        os.makedirs(repo_path, exist_ok=True)
        git.Repo.init(repo_path)
        
        file = SimpleUploadedFile("test.exe", b"malicious payload")
        response = self.client.post(self.upload_url, {'repo_id': repo.repository_id, 'files': [file]})
        self.assertEqual(response.status_code, 200)
        warnings = response.json().get('warnings', [])
        self.assertTrue(any('test.exe' in w for w in warnings))
        self.assertFalse(os.path.exists(os.path.join(repo_path, 'test.exe')))
        
    def test_upload_capacity_limit(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from unittest.mock import patch
        import git
        repo = Repository.objects.create(user=self.user, repo_name='UploadRepo3')
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(repo.repository_id))
        os.makedirs(repo_path, exist_ok=True)
        git.Repo.init(repo_path)
        
        with patch('repository.views.get_dir_size', return_value=(1024*1024*1024)):
            file = SimpleUploadedFile("test.py", b"print('hello')")
            response = self.client.post(self.upload_url, {'repo_id': repo.repository_id, 'files': [file]})
            self.assertEqual(response.status_code, 400)
            self.assertIn('exceeded', response.json().get('error', ''))
