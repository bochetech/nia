"""
Model Adapter settings — extiende BaseServiceSettings con config LLM.
"""
from pydantic import Field, model_validator

from shared.config.base import BaseServiceSettings


class ModelAdapterSettings(BaseServiceSettings):
    service_name: str = "model-adapter"
    port: int = 8005

    # Tenant manager API base (with /api/tenants path).
    # Built from tenant_manager_url inherited from BaseServiceSettings
    # so that TENANT_MANAGER_URL env var is honoured automatically.
    # Override the whole path via TENANT_MANAGER_TENANTS_URL if needed.
    tenant_manager_tenants_url: str = ""

    @model_validator(mode="after")
    def _build_tenants_url(self) -> "ModelAdapterSettings":
        if not self.tenant_manager_tenants_url:
            base = self.tenant_manager_url.rstrip("/")
            self.tenant_manager_tenants_url = f"{base}/api/tenants"
        return self

    # LM Studio
    lm_studio_base_url: str = "http://localhost:1234"
    lm_studio_chat_model: str = "google/gemma-4-e4b"
    lm_studio_embed_model: str = "nomic-ai/nomic-embed-text-v1.5-GGUF"
    lm_studio_timeout_seconds: int = 120

    # Vertex AI
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"
    vertex_ai_chat_model: str = "gemini-1.5-flash-001"
    vertex_ai_pro_model: str = "gemini-1.5-pro-001"
    vertex_ai_embed_model: str = "text-multilingual-embedding-002"

    # OpenAI fallback
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"

    # Generation defaults
    default_temperature: float = 0.3
    default_max_tokens: int = 1024
    stream_chunk_timeout: int = 30


_settings: ModelAdapterSettings | None = None


def get_settings() -> ModelAdapterSettings:
    global _settings
    if _settings is None:
        _settings = ModelAdapterSettings()  # type: ignore[call-arg]
    return _settings
