"""Provider-agnostic LLM client with retries, timeouts, cost tracking and a budget cap."""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import ClassVar, Literal, TypedDict, TypeVar

from pydantic import BaseModel, ValidationError

from agents_core.errors import BudgetExceededError, LLMError, TransientLLMError
from agents_core.llm.pricing import ModelPricing, lookup_pricing
from agents_core.logging import get_logger
from agents_core.models import TokenUsage

T = TypeVar("T", bound=BaseModel)
R = TypeVar("R")

logger = get_logger("llm")

CHARS_PER_TOKEN_ESTIMATE = 4


class Message(BaseModel):
    """A chat message."""

    role: Literal["user", "assistant"]
    content: str


class LLMResponse(BaseModel):
    """A completed LLM call."""

    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0


class LLMClientOptions(TypedDict, total=False):
    """Common keyword options accepted by every client constructor."""

    max_cost_usd: float | None
    timeout_s: float
    max_retries: int
    backoff_base_s: float
    pricing: ModelPricing | None


Prompt = str | Sequence[Message]


def _normalize(prompt: Prompt) -> list[Message]:
    if isinstance(prompt, str):
        return [Message(role="user", content=prompt)]
    return list(prompt)


def extract_json(text: str) -> str:
    """Extract a JSON object/array from an LLM reply (handles code fences and prose)."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1] if "\n" in stripped else ""
        if stripped.rstrip().endswith("```"):
            stripped = stripped.rstrip()[:-3]
        stripped = stripped.strip()
    try:
        json.loads(stripped)
        return stripped
    except json.JSONDecodeError:
        pass
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start, end = stripped.find(open_ch), stripped.rfind(close_ch)
        if start != -1 and end > start:
            candidate = stripped[start : end + 1]
            try:
                json.loads(candidate)
                return candidate
            except json.JSONDecodeError:
                continue
    raise ValueError("No valid JSON found in model output")


class LLMClient(ABC):
    """Base class for LLM clients.

    Subclasses implement :meth:`_complete_raw`; this class adds retries with exponential
    backoff, per-call timeouts, usage/cost accounting, and a hard budget cap.
    """

    provider: ClassVar[str]

    def __init__(
        self,
        model: str,
        *,
        max_cost_usd: float | None = None,
        timeout_s: float = 60.0,
        max_retries: int = 3,
        backoff_base_s: float = 1.0,
        pricing: ModelPricing | None = None,
    ) -> None:
        self.model = model
        self.max_cost_usd = max_cost_usd
        self.timeout_s = timeout_s
        self.max_retries = max_retries
        self.backoff_base_s = backoff_base_s
        self.pricing = pricing or lookup_pricing(self.provider, model)
        self._usage = TokenUsage()

    # ---- accounting -----------------------------------------------------------------

    @property
    def usage(self) -> TokenUsage:
        """A snapshot of cumulative usage for this client."""
        return self._usage.model_copy()

    @property
    def remaining_budget_usd(self) -> float | None:
        if self.max_cost_usd is None:
            return None
        return max(0.0, self.max_cost_usd - self._usage.cost_usd)

    def estimate_cost(
        self, messages: Sequence[Message], system: str | None, max_tokens: int
    ) -> float:
        """Worst-case cost estimate for a call (assumes the full ``max_tokens`` output)."""
        chars = sum(len(m.content) for m in messages) + len(system or "")
        return self.pricing.cost(chars // CHARS_PER_TOKEN_ESTIMATE + 1, max_tokens)

    def _check_budget(
        self, messages: Sequence[Message], system: str | None, max_tokens: int
    ) -> None:
        if self.max_cost_usd is None:
            return
        estimate = self.estimate_cost(messages, system, max_tokens)
        if self._usage.cost_usd + estimate > self.max_cost_usd:
            raise BudgetExceededError(
                f"LLM budget of ${self.max_cost_usd:.4f} would be exceeded "
                f"(spent ${self._usage.cost_usd:.4f}, next call up to ${estimate:.4f})"
            )

    # ---- public API -----------------------------------------------------------------

    async def complete(
        self,
        prompt: Prompt,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = 0.0,
    ) -> LLMResponse:
        """Run a text completion."""
        messages = _normalize(prompt)
        self._check_budget(messages, system, max_tokens)
        response = await self._with_retries(
            lambda: self._complete_raw(messages, system, max_tokens, temperature)
        )
        cost = self.pricing.cost(response.input_tokens, response.output_tokens)
        response = response.model_copy(update={"cost_usd": cost})
        self._usage = self._usage + TokenUsage(
            llm_calls=1,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cost_usd=cost,
        )
        return response

    async def complete_structured(
        self,
        schema: type[T],
        prompt: Prompt,
        *,
        system: str | None = None,
        max_tokens: int = 2048,
        temperature: float | None = 0.0,
        max_repair_attempts: int = 1,
    ) -> T:
        """Run a completion whose output must validate against ``schema``.

        On invalid output the model is shown the error and asked to repair its reply,
        up to ``max_repair_attempts`` times.
        """
        instructions = (
            "Respond with a single JSON object that validates against this JSON Schema. "
            "Output only the JSON, with no prose and no code fences.\n"
            f"JSON Schema:\n{json.dumps(schema.model_json_schema())}"
        )
        full_system = f"{system}\n\n{instructions}" if system else instructions
        messages = _normalize(prompt)
        last_error: Exception | None = None
        for _attempt in range(max_repair_attempts + 1):
            response = await self.complete(
                messages, system=full_system, max_tokens=max_tokens, temperature=temperature
            )
            try:
                return schema.model_validate_json(extract_json(response.text))
            except (ValidationError, ValueError) as exc:
                last_error = exc
                messages = [
                    *messages,
                    Message(role="assistant", content=response.text),
                    Message(
                        role="user",
                        content=(
                            "Your previous reply did not validate against the schema. "
                            f"Error: {exc}\nReply again with only valid JSON."
                        ),
                    ),
                ]
        raise LLMError(f"Model output failed schema validation: {last_error}")

    # ---- internals ------------------------------------------------------------------

    async def _with_retries(self, call: Callable[[], Awaitable[R]]) -> R:
        attempt = 0
        while True:
            try:
                return await asyncio.wait_for(call(), timeout=self.timeout_s)
            except (TransientLLMError, TimeoutError) as exc:
                if attempt >= self.max_retries:
                    raise TransientLLMError(
                        f"LLM call failed after {attempt + 1} attempts: {exc}"
                    ) from exc
                delay = self.backoff_base_s * (2**attempt)
                logger.warning("Transient LLM error (%s); retrying in %.1fs", exc, delay)
                attempt += 1
                await asyncio.sleep(delay)

    @abstractmethod
    async def _complete_raw(
        self,
        messages: list[Message],
        system: str | None,
        max_tokens: int,
        temperature: float | None,
    ) -> LLMResponse:
        """Perform one provider call. Raise :class:`TransientLLMError` for retryable failures."""
