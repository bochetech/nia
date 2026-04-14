"""Orchestrator settings."""
from shared.config.base import BaseServiceSettings


class OrchestratorSettings(BaseServiceSettings):
    service_name: str = "orchestrator"
    port: int = 8001

    # FSM timeouts
    session_idle_timeout_minutes: int = 30
    handoff_timeout_minutes: int = 15
    checkout_expiry_minutes: int = 30

    # Intent detection
    intent_detection_temperature: float = 0.0
    intent_max_tokens: int = 1000  # must be high enough for reasoning models (Gemma, DeepSeek, etc.)

    # Thresholds
    complaint_handoff_threshold: int = 2  # N complaints → handoff
    unresolved_threshold: int = 3         # N FAQ fallbacks → handoff

    # Rate limiting & CORS
    allowed_origins: list[str] = ["*"]
    rate_limit_per_minute: int = 60       # requests por IP por minuto
    rate_limit_chat: str = "60/minute"    # formato slowapi


_settings = None


def get_settings() -> OrchestratorSettings:
    global _settings
    if _settings is None:
        _settings = OrchestratorSettings()  # type: ignore[call-arg]
    return _settings
