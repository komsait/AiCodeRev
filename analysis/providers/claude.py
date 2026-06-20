import requests
from .base import AIProviderInterface, AIProviderError

class ClaudeProvider(AIProviderInterface):
    def __init__(self, api_key, model_name="claude-3-5-sonnet-20240620"):
        if not api_key:
            raise AIProviderError("No API key configured for Anthropic Claude")
        self.api_key = api_key
        self._model_name = model_name

    @property
    def provider_name(self):
        return "Anthropic Claude"

    @property
    def model_name(self):
        return self._model_name

    def _call_api(self, prompt, max_tokens):
        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }
        payload = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            try:
                return data['content'][0]['text']
            except (KeyError, IndexError) as e:
                raise AIProviderError(f"Unexpected response format from Claude: {e}")
        elif response.status_code in (401, 403):
            raise AIProviderError("Invalid API key for Anthropic Claude")
        else:
            raise AIProviderError(f"Anthropic Claude API error ({response.status_code}): {response.text}")
