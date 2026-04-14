"""Tenant Manager settings."""
from shared.config.base import BaseServiceSettings


class TenantManagerSettings(BaseServiceSettings):
    service_name: str = "tenant-manager"
    port: int = 8003

    # Provisioning
    qdrant_collection_prefix: str = "nia_tenant"
    default_rag_config_top_k: int = 8
    tenant_schema_prefix: str = "tenant_"

    # Admin bootstrap
    super_admin_email: str = "admin@nia.local"
    super_admin_password: str = "changeme"

    # URLs de servicios internos (para referencias en widget-config)
    transcript_service_url: str = "http://nia_transcript:8008"

    # URLs para analytics / RAG stats
    rag_url: str = "http://nia_rag:8002"
    qdrant_url: str = "http://nia_qdrant:6333"


_settings: TenantManagerSettings | None = None


def get_settings() -> TenantManagerSettings:
    global _settings
    if _settings is None:
        _settings = TenantManagerSettings()  # type: ignore[call-arg]
    return _settings
