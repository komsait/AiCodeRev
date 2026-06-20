import os
import tempfile
from django.test import TestCase
from django.contrib.auth import get_user_model
from repository.models import Repository
from .models import AnalysisReport, CodeSmell
from .services import AIService
from unittest.mock import patch

User = get_user_model()

class AnalysisTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pw')
        self.repo = Repository.objects.create(user=self.user, repo_name='TestRepo')

    @patch('analysis.providers.factory.AIProviderFactory.get_provider')
    def test_extract_and_send_extensions(self, mock_get_provider):
        mock_provider = mock_get_provider.return_value
        mock_provider.detect_code_smells.return_value = '[{"smell_type": "Test Smell", "severity_level": "Major"}]'
        with tempfile.TemporaryDirectory() as temp_dir:
            with open(os.path.join(temp_dir, 'test.py'), 'w') as f:
                f.write('def foo(): pass\n' * 50)
            with open(os.path.join(temp_dir, 'test.txt'), 'w') as f:
                f.write('unsupported file')
                
            response = AIService.extract_and_send(temp_dir)
            self.assertIn("smells", response)
            smells = response["smells"]
            processed_files = [s.get('file_path', '') for s in smells]
            self.assertTrue(any('test.py' in p for p in processed_files))
            self.assertFalse(any('test.txt' in p for p in processed_files))

    @patch('analysis.providers.factory.AIProviderFactory.get_provider')
    def test_extract_and_send_empty(self, mock_get_provider):
        with tempfile.TemporaryDirectory() as temp_dir:
            response = AIService.extract_and_send(temp_dir)
            self.assertIn("smells", response)
            self.assertEqual(response["smells"][0]["smell_type"], "No Analytical Findings")

    @patch('analysis.providers.factory.AIProviderFactory.get_provider')
    def test_classify_and_store(self, mock_get_provider):
        mock_provider = mock_get_provider.return_value
        mock_provider.provider_name = 'TestProvider'
        mock_provider.model_name = 'test-model'
        
        fake_response = {
            "smells": [
                {
                    "smell_type": "Fake Smell",
                    "severity_level": "Major",
                    "file_path": "fake.py",
                    "description": "Just a test"
                },
                {
                    "smell_type": "Minor Issue",
                    "severity_level": "InvalidSeverity",
                    "file_path": "fake2.py",
                    "description": "Another test"
                }
            ]
        }
        report = AIService.classify_and_store(fake_response, self.repo)
        self.assertEqual(AnalysisReport.objects.count(), 1)
        self.assertEqual(CodeSmell.objects.count(), 2)
        
        major_smell = CodeSmell.objects.get(file_path="fake.py")
        self.assertEqual(major_smell.smell_type, "Fake Smell")
        self.assertEqual(major_smell.severity_level, "Major")
        
        # Test default severity normalization for invalid severities
        minor_smell = CodeSmell.objects.get(file_path="fake2.py")
        self.assertEqual(minor_smell.severity_level, "Moderate")
