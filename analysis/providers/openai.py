import requests
from .base import AIProviderInterface, AIProviderError

class OpenAIProvider(AIProviderInterface):
    def __init__(self, api_key, model_name="gpt-4o"):
        if not api_key:
            raise AIProviderError("No API key configured for OpenAI")
        self.api_key = api_key
        self._model_name = model_name

    @property
    def provider_name(self):
        return "OpenAI"

    @property
    def model_name(self):
        return self._model_name

    def _call_api(self, prompt, max_tokens):
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.2
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            try:
                return data['choices'][0]['message']['content']
            except (KeyError, IndexError) as e:
                raise AIProviderError(f"Unexpected response format from OpenAI: {e}")
        elif response.status_code in (401, 403):
            raise AIProviderError("Invalid API key for OpenAI")
        else:
            raise AIProviderError(f"OpenAI API error ({response.status_code}): {response.text}")
