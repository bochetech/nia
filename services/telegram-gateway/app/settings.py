"""Telegram Gateway settings."""
from shared.config.base import BaseServiceSettings


class TelegramGatewaySettings(BaseServiceSettings):
    service_name: str = "telegram-gateway"
    port: int = 8010

    # URLs de servicios internos
    orchestrator_url: str = "http://nia_orchestrator:8001"
    tenant_manager_url: str = "http://nia_tenant_manager:8003"

    # Master JWT secret (mismo que tenant-manager para crear widget tokens)
    # Se hereda de BaseServiceSettings como jwt_secret


_settings: TelegramGatewaySettings | None = None


def get_settings() -> TelegramGatewaySettings:
    global _settings
    if _settings is None:
        _settings = TelegramGatewaySettings()  # type: ignore[call-arg]
    return _settings
