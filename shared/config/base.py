"""
Configuración base compartida por todos los servicios.
Cada servicio hereda de BaseSettings y añade sus propias variables.
"""
from enum import Enum
from pydantic_settings import BaseSettings, SettingsConfigDict


class Environment(str, Enum):
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class ModelProvider(str, Enum):
    LMSTUDIO = "lmstudio"
    VERTEXAI = "vertexai"
    OPENAI = "openai"


class BaseServiceSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Entorno ──────────────────────────────────────────────────────────────
    env: Environment = Environment.DEVELOPMENT
    log_level: str = "INFO"
    json_logs: bool = False
    service_name: str = "nia-service"

    # ── Base de datos ─────────────────────────────────────────────────────────
    postgres_dsn: str = "postgresql+asyncpg://nia_user:nia_secret@localhost:5432/nia_dev"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379"

    # ── JWT ───────────────────────────────────────────────────────────────────
    jwt_secret: str = "dev-jwt-secret-change-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 240  # 4 horas para widget tokens

    # ── URLs de servicios internos ────────────────────────────────────────────
    model_adapter_url: str = "http://localhost:8005"
    rag_service_url: str = "http://localhost:8002"
    recommender_url: str = "http://localhost:8004"
    tenant_manager_url: str = "http://localhost:8003"
    checkout_url: str = "http://localhost:8006"
    handoff_url: str = "http://localhost:8007"
    transcript_url: str = "http://localhost:8008"

    # ── Modelo ────────────────────────────────────────────────────────────────
    model_provider: ModelProvider = ModelProvider.LMSTUDIO

    @property
    def is_development(self) -> bool:
        return self.env == Environment.DEVELOPMENT

    @property
    def is_production(self) -> bool:
        return self.env == Environment.PRODUCTION
