"""Per-model pricing used for cost tracking and budget enforcement.

Prices are USD per million tokens and are *estimates*: they go stale, so pass an explicit
:class:`ModelPricing` to a client when accuracy matters. Unknown models fall back to a
deliberately expensive price so budget caps err on the safe side.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class ModelPricing(BaseModel):
    """USD price per one million input/output tokens."""

    model_config = ConfigDict(frozen=True)

    input_per_mtok: float
    output_per_mtok: float

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens * self.input_per_mtok + output_tokens * self.output_per_mtok
        ) / 1_000_000


FREE = ModelPricing(input_per_mtok=0.0, output_per_mtok=0.0)
CONSERVATIVE_FALLBACK = ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0)

# Matched by longest model-name prefix within a provider.
DEFAULT_PRICING: dict[str, dict[str, ModelPricing]] = {
    "anthropic": {
        "claude-opus": ModelPricing(input_per_mtok=15.0, output_per_mtok=75.0),
        "claude-sonnet": ModelPricing(input_per_mtok=3.0, output_per_mtok=15.0),
        "claude-haiku": ModelPricing(input_per_mtok=1.0, output_per_mtok=5.0),
    },
    "openai": {
        "gpt-4o-mini": ModelPricing(input_per_mtok=0.15, output_per_mtok=0.6),
        "gpt-4o": ModelPricing(input_per_mtok=2.5, output_per_mtok=10.0),
        "gpt-4.1-nano": ModelPricing(input_per_mtok=0.1, output_per_mtok=0.4),
        "gpt-4.1-mini": ModelPricing(input_per_mtok=0.4, output_per_mtok=1.6),
        "gpt-4.1": ModelPricing(input_per_mtok=2.0, output_per_mtok=8.0),
    },
    "mock": {"": FREE},
}


def lookup_pricing(provider: str, model: str) -> ModelPricing:
    """Return pricing for ``model`` (longest prefix match), or a conservative fallback."""
    table = DEFAULT_PRICING.get(provider, {})
    matches = [prefix for prefix in table if model.startswith(prefix)]
    if not matches:
        return CONSERVATIVE_FALLBACK
    return table[max(matches, key=len)]
