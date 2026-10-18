"""Environment-driven settings (reads ``.env`` if present). Secrets never have defaults.

``AGENTS_LIB_ENV_FILE`` chooses the env file (default ``.env`` in the current directory);
set it to an empty string to read environment variables only, as the test suite does.
"""

import os

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
    local_llm_reasoning_effort: str = "none"  # empty: don't send the field

    default_llm_provider: str = "local"
    default_llm_model: str | None = None
    max_cost_usd: float = 1.0
    log_level: str = "INFO"


ENV_FILE_VAR = "AGENTS_LIB_ENV_FILE"


def get_settings() -> Settings:
    """Load settings fresh from the environment (and the env file, if any)."""
    env_file = os.environ.get(ENV_FILE_VAR, ".env")
    return Settings(_env_file=env_file or None)  # type: ignore[call-arg]
