"""Environment-driven settings (reads ``.env`` if present). Secrets never have defaults."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global settings for agents-lib, loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    github_token: SecretStr | None = None

    local_llm_base_url: str = "http://localhost:11434"
    local_llm_api_key: SecretStr | None = None

    default_llm_provider: str = "local"
    default_llm_model: str | None = None
    max_cost_usd: float = 1.0
    log_level: str = "INFO"


def get_settings() -> Settings:
    """Load settings fresh from the environment."""
    return Settings()
