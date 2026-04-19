"""Factory de providers — instancia el provider correcto según ENV o tenant config."""
from __future__ import annotations

import httpx

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


def create_provider_for_tenant(tenant_id: str, settings: ModelAdapterSettings) -> ModelProviderAdapter:
    """
    Creates a provider scoped to a tenant's ai_config connection settings.
    Falls back to the server-level default provider if the tenant has no custom
    endpoint_url configured.

    The tenant config is fetched synchronously from the tenant-manager service.
    Result is NOT cached — tenant admins can change config and see it take effect
    on the next request without restarting the model-adapter.
    """
    try:
        resp = httpx.get(
            f"{settings.tenant_manager_tenants_url}/{tenant_id}/config",
            timeout=2.0,
        )
        if resp.status_code != 200:
            return create_provider(settings)

        tenant_cfg = resp.json().get("data", {})
        ai_cfg = tenant_cfg.get("ai_config", {})

        endpoint_url = ai_cfg.get("primary_endpoint_url", "").strip()
        api_key      = ai_cfg.get("primary_api_key", "").strip()
        model        = ai_cfg.get("primary_model", "").strip()
        provider_type = ai_cfg.get("primary_provider", "").strip()

        # No custom endpoint → use server default
        if not endpoint_url and not api_key:
            # But still override model if specified
            default = create_provider(settings)
            if model and hasattr(default, "_chat_model"):
                default._chat_model = model
            return default

        # Build an ad-hoc LMStudio-compat provider with the tenant's connection
        from app.providers.lmstudio import LMStudioProvider
        provider = LMStudioProvider(
            base_url=endpoint_url or settings.lm_studio_base_url,
            chat_model=model or settings.lm_studio_chat_model,
            embed_model=settings.lm_studio_embed_model,
            timeout=settings.lm_studio_timeout_seconds,
        )
        if api_key:
            provider._client.headers["Authorization"] = f"Bearer {api_key}"
        return provider

    except Exception:
        # Network error or tenant not found → server default
        return create_provider(settings)
