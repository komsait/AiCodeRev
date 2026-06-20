import os
from .base import AIProviderError
from .gemini import GeminiProvider
from .openai import OpenAIProvider
from .claude import ClaudeProvider

class AIProviderFactory:
    
    @staticmethod
    def get_provider():
        # Avoid circular imports if models import factory or vice-versa
        from ai_config.models import AIModelConfiguration
        
        # 1. Query AIModelConfiguration for active config
        active_config = AIModelConfiguration.objects.filter(is_active=True).first()
        
        if active_config:
            if active_config.provider_name == 'openai':
                api_key = os.environ.get('OPENAI_API_KEY')
                if not api_key:
                    raise AIProviderError("OPENAI_API_KEY is not configured in the environment variables.")
                return OpenAIProvider(api_key=api_key, model_name=active_config.model_name)
            elif active_config.provider_name == 'gemini':
                api_key = os.environ.get('GEMINI_API_KEY')
                if not api_key:
                    raise AIProviderError("GEMINI_API_KEY is not configured in the environment variables.")
                return GeminiProvider(api_key=api_key, model_name=active_config.model_name)
            elif active_config.provider_name == 'claude':
                api_key = os.environ.get('ANTHROPIC_API_KEY')
                if not api_key:
                    raise AIProviderError("ANTHROPIC_API_KEY is not configured in the environment variables.")
                return ClaudeProvider(api_key=api_key, model_name=active_config.model_name)
            else:
                raise AIProviderError(f"Unsupported provider: {active_config.provider_name}")
                
        # 2. Fall back to GEMINI_API_KEY env var
        gemini_api_key = os.environ.get('GEMINI_API_KEY')
        if gemini_api_key:
            return GeminiProvider(api_key=gemini_api_key)
            
        raise AIProviderError("No AI provider is configured and no fallback GEMINI_API_KEY was found.")

    @staticmethod
    def get_provider_name():
        try:
            provider = AIProviderFactory.get_provider()
            return f"{provider.provider_name} / {provider.model_name}"
        except AIProviderError:
            return "No Provider Configured"
