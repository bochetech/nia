"""Factory de providers — instancia el provider correcto según ENV."""
from __future__ import annotations

from shared.config.base import ModelProvider

from app.providers.base import ModelProviderAdapter
from app.settings import ModelAdapterSettings

_provider_instance: ModelProviderAdapter | None = None


def create_provider(settings: ModelAdapterSettings) -> ModelProviderAdapter:
    global _provider_instance

    if _provider_instance is not None:
        return _provider_instance

    if settings.model_provider == ModelProvider.LMSTUDIO:
        from app.providers.lmstudio import LMStudioProvider
        _provider_instance = LMStudioProvider(
            base_url=settings.lm_studio_base_url,
            chat_model=settings.lm_studio_chat_model,
            embed_model=settings.lm_studio_embed_model,
            timeout=settings.lm_studio_timeout_seconds,
        )

    elif settings.model_provider == ModelProvider.VERTEXAI:
        from app.providers.vertexai import VertexAIProvider
        _provider_instance = VertexAIProvider(
            project=settings.vertex_ai_project,
            location=settings.vertex_ai_location,
            chat_model=settings.vertex_ai_chat_model,
            pro_model=settings.vertex_ai_pro_model,
            embed_model=settings.vertex_ai_embed_model,
        )

    elif settings.model_provider == ModelProvider.OPENAI:
        from app.providers.lmstudio import LMStudioProvider  # OpenAI es compatible
        _provider_instance = LMStudioProvider(
            base_url="https://api.openai.com/v1",
            chat_model=settings.openai_chat_model,
            embed_model="text-embedding-3-small",
            timeout=60,
        )
        # Monkey-patch el API key header
        _provider_instance._client.headers["Authorization"] = f"Bearer {settings.openai_api_key}"

    else:
        raise ValueError(f"Unknown model provider: {settings.model_provider}")

    return _provider_instance
