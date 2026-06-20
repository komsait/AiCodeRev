def ai_provider_context(request):
    from analysis.providers.factory import AIProviderFactory
    from analysis.providers.base import AIProviderError

    try:
        active_ai_provider = AIProviderFactory.get_provider_name()
    except AIProviderError:
        active_ai_provider = "No Provider Configured"

    return {
        'active_ai_provider': active_ai_provider,
    }
