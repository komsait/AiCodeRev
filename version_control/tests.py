import os
import shutil
import git
from django.test import TestCase
from django.conf import settings
from django.contrib.auth import get_user_model
from repository.models import Repository
from .services import GitService

User = get_user_model()

class GitServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw')
        self.repo = Repository.objects.create(user=self.user, repo_name='TestRepo')
        self.repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(self.repo.repository_id))
        
        # Init physically
        os.makedirs(self.repo_path, exist_ok=True)
        git.Repo.init(self.repo_path)
        
    def tearDown(self):
        # Cleanup physically
        user_workspace = os.path.join(settings.MEDIA_ROOT, str(self.user.id))
        if os.path.exists(user_workspace):
            shutil.rmtree(user_workspace, ignore_errors=True)
            
    def test_get_status_empty(self):
        status = GitService.get_status(self.repo_path)
        self.assertEqual(status['changed'], [])
        self.assertEqual(status['untracked'], [])
        self.assertEqual(status['staged'], [])
        
    def test_commit_file(self):
        # Create a file
        test_file = os.path.join(self.repo_path, 'hello.txt')
        with open(test_file, 'w') as f:
            f.write("Hello World")
            
        status = GitService.get_status(self.repo_path)
        self.assertIn('hello.txt', status['untracked'])
        
        commit_hash = GitService.commit_all(self.repo_path, "Initial commit")
        self.assertIsNotNone(commit_hash)
        
        logs = GitService.get_log(self.repo_path)
        self.assertEqual(len(logs), 1)
        self.assertEqual(logs[0]['message'], "Initial commit")

    def test_auto_generate_commit_message(self):
        from unittest.mock import patch
        from django.test import Client
        from django.urls import reverse
        
        test_file = os.path.join(self.repo_path, 'hello.txt')
        with open(test_file, 'w') as f:
            f.write("print('hello auto update')")
            
        client = Client()
        client.login(username='tester', password='pw')
        url = reverse('commits')
        
        with patch('analysis.providers.factory.AIProviderFactory.get_provider') as mock_get_provider, \
             patch('version_control.services.GitService.get_diff_summary', return_value='mock diff'):
            mock_provider = mock_get_provider.return_value
            mock_provider.generate_commit_message.return_value = "Auto commit mock"
            res_msg = client.post(url, {
                'action': 'generate_msg',
                'repo_id': self.repo.repository_id
            })
            self.assertEqual(res_msg.json().get('message'), "Auto commit mock")
            
            response = client.post(url, {
                'action': 'commit',
                'repo_id': self.repo.repository_id,
                'commit_message': 'Auto commit mock'
            })
            
        self.assertEqual(response.status_code, 302)
        logs = GitService.get_log(self.repo_path)
        self.assertTrue(len(logs) > 0)
        self.assertEqual(logs[0]['message'], "Auto commit mock")

class HistoryViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw')
        self.repo = Repository.objects.create(user=self.user, repo_name='TestRepo')
        self.repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(self.repo.repository_id))
        os.makedirs(self.repo_path, exist_ok=True)
        git.Repo.init(self.repo_path)
        
    def tearDown(self):
        user_workspace = os.path.join(settings.MEDIA_ROOT, str(self.user.id))
        if os.path.exists(user_workspace):
            shutil.rmtree(user_workspace, ignore_errors=True)

    def test_parse_git_diff_helper(self):
        from version_control.views import parse_git_diff
        diff_output = (
            "diff --git a/hello.txt b/hello.txt\n"
            "index 0000000..4d7fb97\n"
            "--- a/hello.txt\n"
            "+++ b/hello.txt\n"
            "@@ -1,3 +1,4 @@\n"
            " hello\n"
            "-world\n"
            "+there\n"
            "+friend\n"
        )
        files = parse_git_diff(diff_output)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]['filename'], 'hello.txt')
        self.assertEqual(files[0]['status'], 'modified')
        self.assertEqual(len(files[0]['hunks']), 1)
        
        hunk = files[0]['hunks'][0]
        # Left side should contain hello (normal), world (deleted), and a placeholder
        self.assertEqual(len(hunk['left_lines']), 4)
        self.assertEqual(hunk['left_lines'][0]['number'], 1)
        self.assertEqual(hunk['left_lines'][0]['class'], 'line-normal')
        self.assertEqual(hunk['left_lines'][1]['number'], 2)
        self.assertEqual(hunk['left_lines'][1]['class'], 'line-deleted')
        self.assertEqual(hunk['left_lines'][2]['number'], '')
        self.assertEqual(hunk['left_lines'][2]['class'], 'line-placeholder')
        
        # Right side should contain hello (normal), placeholder, there (added), friend (added)
        self.assertEqual(len(hunk['right_lines']), 4)
        self.assertEqual(hunk['right_lines'][0]['number'], 1)
        self.assertEqual(hunk['right_lines'][1]['number'], '')
        self.assertEqual(hunk['right_lines'][2]['number'], 2)
        self.assertEqual(hunk['right_lines'][2]['class'], 'line-added')
        self.assertEqual(hunk['right_lines'][3]['number'], 3)
        self.assertEqual(hunk['right_lines'][3]['class'], 'line-added')

    def test_history_view_diff_context(self):
        from django.test import Client
        from django.urls import reverse
        
        # Create and commit a file to have a commit hash
        test_file = os.path.join(self.repo_path, 'hello.txt')
        with open(test_file, 'w') as f:
            f.write("hello")
        commit_hash = GitService.commit_all(self.repo_path, "Initial commit")
        
        client = Client()
        client.login(username='tester', password='pw')
        url = reverse('history')
        
        # GET request with repo and hash
        response = client.get(url, {
            'repo': self.repo.repository_id,
            'hash': commit_hash
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('diff_files', response.context)
        diff_files = response.context['diff_files']
        self.assertTrue(len(diff_files) > 0)
        self.assertEqual(diff_files[0]['filename'], 'hello.txt')
