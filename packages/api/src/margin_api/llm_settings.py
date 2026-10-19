"""Model settings over HTTP, for the web UI: which provider and model runs use, the keys
(never sent back, only whether one is set and its last four characters), the models each
provider offers, and a connection check. Changes are saved in the user's settings file and
apply to the next run; nothing needs a restart."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException
from margin_core.config import (
    Source,
    get_settings,
    save_user_config,
    setting_sources,
    user_config_path,
)
from margin_core.errors import LLMError
from margin_core.llm.catalog import PROVIDERS, check_connection, list_models
from margin_core.llm.factory import DEFAULT_MODELS, PROVIDER_MODEL_SETTING, resolve_model
from pydantic import BaseModel, Field, SecretStr

ProviderId = Literal["local", "anthropic", "openai"]
KEY_SETTING: dict[str, str] = {
    "local": "local_llm_api_key",
    "anthropic": "anthropic_api_key",
    "openai": "openai_api_key",
}


class ProviderView(BaseModel):
    id: ProviderId
    label: str
    needs_key: bool
    on_device: bool = Field(
        description="False: prompts, such as samples of code, leave this machine."
    )
    default_model: str
    model: str = Field(description="The model runs use with this provider.")
    model_source: Source
    key_set: bool
    key_hint: str | None = Field(description="Last four characters of the key, never the key.")
    key_source: Source


class LLMSettingsView(BaseModel):
    provider: ProviderId
    provider_source: Source
    local_base_url: str
    local_base_url_source: Source
    max_cost_usd: float = Field(description="Spending cap per run, for hosted providers.")
    providers: list[ProviderView]
    saving_enabled: bool
    settings_file: str | None


class LLMSettingsUpdate(BaseModel):
    """Only the fields present change. For models and keys, an empty string removes the
    saved value (the next source in line applies again)."""

    model_config = {"extra": "forbid"}

    provider: ProviderId | None = None
    local_base_url: str | None = None
    models: dict[ProviderId, str] | None = None
    keys: dict[ProviderId, str] | None = None
    max_cost_usd: float | None = Field(default=None, ge=0)


class ModelList(BaseModel):
    provider: ProviderId
    models: list[str]


class ConnectionRequest(BaseModel):
    model_config = {"extra": "forbid"}

    provider: ProviderId | None = None
    model: str | None = None


class ConnectionResult(BaseModel):
    ok: bool
    provider: str
    model: str
    latency_ms: int | None
    message: str


def _hint(secret: SecretStr | None) -> str | None:
    value = secret.get_secret_value() if secret else ""
    return f"…{value[-4:]}" if len(value) >= 8 else ("set" if value else None)


def current_view() -> LLMSettingsView:
    settings = get_settings()
    sources = setting_sources()
    provider = settings.default_llm_provider.lower()
    views = []
    for p in PROVIDERS:
        key = getattr(settings, KEY_SETTING[p.id])
        model_field = PROVIDER_MODEL_SETTING[p.id]
        views.append(
            ProviderView(
                id=p.id,  # type: ignore[arg-type]
                label=p.label,
                needs_key=p.needs_key,
                on_device=p.on_device,
                default_model=DEFAULT_MODELS[p.id],
                model=resolve_model(p.id, settings),
                model_source=sources.get(model_field, "default"),
                key_set=bool(key and key.get_secret_value()),
                key_hint=_hint(key),
                key_source=sources.get(KEY_SETTING[p.id], "default"),
            )
        )
    path = user_config_path()
    return LLMSettingsView(
        provider=provider if provider in KEY_SETTING else "local",  # type: ignore[arg-type]
        provider_source=sources["default_llm_provider"],
        local_base_url=settings.local_llm_base_url,
        local_base_url_source=sources["local_llm_base_url"],
        max_cost_usd=settings.max_cost_usd,
        providers=views,
        saving_enabled=path is not None,
        settings_file=str(path) if path else None,
    )


router = APIRouter(prefix="/settings/llm", tags=["settings"])


@router.get("", response_model=LLMSettingsView)
def get_llm_settings() -> LLMSettingsView:
    return current_view()


@router.put("", response_model=LLMSettingsView)
def update_llm_settings(update: LLMSettingsUpdate) -> LLMSettingsView:
    changes: dict[str, object] = {}
    if update.provider is not None:
        changes["default_llm_provider"] = update.provider
    if update.local_base_url is not None:
        url = update.local_base_url.strip()
        if url and not url.startswith(("http://", "https://")):
            raise HTTPException(422, "The server address must start with http:// or https://")
        changes["local_llm_base_url"] = url
    for provider, model in (update.models or {}).items():
        changes[PROVIDER_MODEL_SETTING[provider]] = model.strip()
    for provider, key in (update.keys or {}).items():
        changes[KEY_SETTING[provider]] = key.strip()
    if update.max_cost_usd is not None:
        changes["max_cost_usd"] = update.max_cost_usd
    if changes:
        try:
            save_user_config(changes)
        except RuntimeError as exc:  # saving is turned off
            raise HTTPException(409, str(exc)) from exc
    return current_view()


@router.get("/models", response_model=ModelList)
async def get_models(provider: ProviderId) -> ModelList:
    try:
        return ModelList(provider=provider, models=await list_models(provider))
    except LLMError as exc:
        raise HTTPException(502, str(exc)) from exc


@router.post("/test", response_model=ConnectionResult)
async def test_connection(request: ConnectionRequest) -> ConnectionResult:
    check = await check_connection(request.provider, request.model)
    return ConnectionResult(**check.__dict__)
