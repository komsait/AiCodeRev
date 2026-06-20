from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from repository.models import Repository
from analysis.models import AnalysisReport, CodeSmell
from .models import RefactoringSuggestion

User = get_user_model()

class RefactoringTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw')
        self.repo = Repository.objects.create(user=self.user, repo_name='TestRepo')
        self.report = AnalysisReport.objects.create(repository=self.repo, ai_model='TestModel')
        self.smell = CodeSmell.objects.create(
            report=self.report,
            smell_type='Test Smell',
            severity_level='Minor',
            file_path='test.py',
            description='Test desc'
        )

    def test_suggestion_creation(self):
        suggestion = RefactoringSuggestion.objects.create(
            smell=self.smell, 
            suggestion_text='def test(): pass'
        )
        self.assertEqual(RefactoringSuggestion.objects.count(), 1)
        self.assertEqual(suggestion.status, 'Pending')

    def test_accept_suggestion(self):
        client = Client()
        client.login(username='tester', password='pw')
        suggestion = RefactoringSuggestion.objects.create(
            smell=self.smell, 
            suggestion_text='def test(): pass'
        )
        import os
        from django.conf import settings
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(self.repo.repository_id))
        os.makedirs(repo_path, exist_ok=True)
        with open(os.path.join(repo_path, 'test.py'), 'w') as f:
            f.write("def original_code(): pass")
            
        url = reverse('refactoring')
        response = client.post(url, {
            'suggestion_id': suggestion.suggestion_id,
            'action': 'accept'
        })
        self.assertEqual(response.status_code, 302)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, 'Accepted')
        
    def test_reject_suggestion(self):
        client = Client()
        client.login(username='tester', password='pw')
        suggestion = RefactoringSuggestion.objects.create(
            smell=self.smell, 
            suggestion_text='def test(): pass'
        )
        url = reverse('refactoring')
        response = client.post(url, {
            'suggestion_id': suggestion.suggestion_id,
            'action': 'reject'
        })
        self.assertEqual(response.status_code, 302)
        suggestion.refresh_from_db()
        self.assertEqual(suggestion.status, 'Rejected')

    def test_tune_suggestion(self):
        client = Client()
        client.login(username='tester', password='pw')
        
        import os
        from django.conf import settings
        repo_path = os.path.join(settings.MEDIA_ROOT, str(self.user.id), str(self.repo.repository_id))
        os.makedirs(repo_path, exist_ok=True)
        with open(os.path.join(repo_path, 'test.py'), 'w') as f:
            f.write("def original_code(): pass")

        from unittest.mock import patch
        with patch('analysis.services.AIService.suggest_refactoring') as mock_suggest:
            mock_suggest.return_value = 'def test_tuned(): pass'
            
            url = reverse('refactoring')
            response = client.post(url, {
                'action': 'tune',
                'smell_id': str(self.smell.smell_id),
                'instructions': 'Use list comprehension'
            }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
            
            self.assertEqual(response.status_code, 200)
            data = response.json()
            self.assertTrue(data['success'])
            self.assertIn('left_lines', data)
            self.assertIn('right_lines', data)
            
            suggestion = RefactoringSuggestion.objects.get(suggestion_id=data['suggestion_id'])
            self.assertEqual(suggestion.suggestion_text, 'def test_tuned(): pass')
