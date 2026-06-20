import requests
from .base import AIProviderInterface, AIProviderError

class GeminiProvider(AIProviderInterface):
    def __init__(self, api_key, model_name="gemini-2.5-flash"):
        if not api_key:
            raise AIProviderError("No API key configured for Google Gemini")
        self.api_key = api_key
        self._model_name = model_name

    @property
    def provider_name(self):
        return "Google Gemini"

    @property
    def model_name(self):
        return self._model_name

    def _call_api(self, prompt, max_tokens):
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        headers = {'Content-Type': 'application/json'}
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": 0.2
            }
        }
        
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            data = response.json()
            try:
                return data['candidates'][0]['content']['parts'][0]['text']
            except (KeyError, IndexError) as e:
                raise AIProviderError(f"Unexpected response format from Gemini: {e}")
        elif response.status_code in (401, 403):
            raise AIProviderError("Invalid API key for Google Gemini")
        else:
            raise AIProviderError(f"Google Gemini API error ({response.status_code}): {response.text}")
