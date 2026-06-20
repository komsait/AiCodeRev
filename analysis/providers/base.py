import time
from abc import ABC, abstractmethod

class AIProviderError(Exception):
    """Custom exception for all provider errors."""
    pass

class AIProviderInterface(ABC):
    
    @property
    @abstractmethod
    def provider_name(self):
        pass
        
    @property
    @abstractmethod
    def model_name(self):
        pass

    @abstractmethod
    def _call_api(self, prompt, max_tokens):
        """Abstract low-level API call, returns raw text string."""
        pass
        
    def _strip_markdown_fences(self, text):
        """Strip markdown code fences (```json or ```) from AI response"""
        text = text.strip()
        if text.startswith('```'):
            lines = text.split('\n')
            if len(lines) >= 2:
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines[-1].strip() == '```':
                    lines = lines[:-1]
                text = '\n'.join(lines)
        return text.strip()

    def _execute_with_retry(self, prompt, max_tokens, retries=3):
        import time
        attempt = 0
        while attempt < retries:
            try:
                response = self._call_api(prompt, max_tokens)
                return self._strip_markdown_fences(response)
            except Exception as e:
                attempt += 1
                if attempt == retries:
                    raise AIProviderError(f"Provider {self.provider_name} failed after {retries} attempts: {str(e)}")
                time.sleep(2 ** attempt)  # Exponential backoff

    def detect_code_smells(self, code, file_path, language, chunk_start_line):
        prompt = (
            f"You are an expert AI code reviewer analyzing code for maintainability issues.\n"
            f"Analyze the following {language} code file from '{file_path}'.\n"
            f"Detect code smells such as Long Method, Large Class, Duplicate Code, Data Clumps, and overly complex logic.\n"
            f"Only return a valid JSON array of objects. Do not include any other text.\n"
            f"Each object must have exactly these keys: 'smell_type', 'severity_level' (Minor, Moderate, Major), 'description', 'start_line', 'end_line'.\n\n"
            f"Code file content:\n```\n{code}\n```"
        )
        return self._execute_with_retry(prompt, max_tokens=4000)

    def generate_refactoring(self, code_smell, original_code, instructions=None):
        prompt = (
            f"You are an expert software engineer.\n"
            f"The following code smell was detected:\n"
            f"Type: {code_smell.smell_type}\n"
            f"Severity: {code_smell.severity_level}\n"
            f"Description: {code_smell.description}\n\n"
            f"Original Code:\n```\n{original_code}\n```\n\n"
        )
        if instructions:
            prompt += f"Specific user instructions for tuning the refactoring:\n{instructions}\n\n"
            
        prompt += (
            f"Provide a refactored version of this code that fixes the issue.\n"
            f"Return ONLY the refactored code. Do not include markdown formatting or explanations."
        )
        return self._execute_with_retry(prompt, max_tokens=2000)

    def generate_commit_message(self, diff_summary):
        prompt = (
            f"You are an expert developer writing commit messages.\n"
            f"Generate a clear, concise, and descriptive Git commit message based on the following changes.\n"
            f"Use the imperative mood (e.g., 'Add feature' not 'Added feature').\n"
            f"Return ONLY the commit message text. Do not include any markdown or explanations.\n\n"
            f"Changes summary:\n{diff_summary}"
        )
        return self._execute_with_retry(prompt, max_tokens=300)
