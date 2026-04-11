"""Recommender settings."""
from shared.config.base import BaseServiceSettings


class RecommenderSettings(BaseServiceSettings):
    service_name: str = "recommender"
    port: int = 8004


_settings = None


def get_settings() -> RecommenderSettings:
    global _settings
    if _settings is None:
        _settings = RecommenderSettings()  # type: ignore[call-arg]
    return _settings
