"""Bokun Skill Service — settings."""
from shared.config.base import BaseServiceSettings


class BokunSettings(BaseServiceSettings):
    service_name: str = "bokun"
    port: int = 8011

    # Bokun API credentials
    bokun_access_key: str = ""
    bokun_secret_key: str = ""
    bokun_api_base_url: str = "https://api.bokun.io"

    # Default currency for availability queries
    bokun_default_currency: str = "USD"
    # Default language for activity data
    bokun_default_lang: str = "EN"


_settings: BokunSettings | None = None


def get_settings() -> BokunSettings:
    global _settings
    if _settings is None:
        _settings = BokunSettings()  # type: ignore[call-arg]
    return _settings
