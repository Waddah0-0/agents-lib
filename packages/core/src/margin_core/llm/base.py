"""Provider-agnostic LLM client with retries, timeouts, cost tracking and a budget cap.

A client is long-lived and may be shared. Each agent run talks to a :class:`LLMSession`
opened from it (see :meth:`LLMClient.session`), so usage, warnings and the budget are
tracked per run while the client keeps lifetime totals.
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable, Sequence
from typing import Any, ClassVar, Literal, TypedDict, TypeVar

from pydantic import BaseModel, Field, ValidationError

from margin_core.errors import BudgetExceededError, LLMError, TransientLLMError
from margin_core.llm.pricing import ModelPricing, lookup_pricing
from margin_core.logging import get_logger
from margin_core.models import TokenUsage

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
    warnings: list[str] = Field(
        default_factory=list, description="Problems noticed by the provider, e.g. truncation."
    )


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
        self.parent: LLMClient | None = None
        self._usage = TokenUsage()
        self._warnings: list[str] = []

    def session(self, *, max_cost_usd: float | None = None) -> LLMSession:
        """Open a per-run view of this client with its own usage, warnings and budget.

        Calls through the session also count toward this client (and its budget, if any).
        """
        return LLMSession(self, max_cost_usd=max_cost_usd)

    async def context_window(self) -> int | None:
        """The model's context window in tokens, if the provider can tell; else ``None``."""
        return None

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

    @property
    def warnings(self) -> list[str]:
        """Distinct provider warnings collected so far, in order of first appearance."""
        return list(self._warnings)

    def _record(self, usage: TokenUsage, warnings: Sequence[str]) -> None:
        self._usage = self._usage + usage
        for warning in warnings:
            if warning not in self._warnings:
                self._warnings.append(warning)
        if self.parent is not None:
            self.parent._record(usage, warnings)

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

    def _check_budgets(
        self, messages: Sequence[Message], system: str | None, max_tokens: int
    ) -> None:
        self._check_budget(messages, system, max_tokens)
        if self.parent is not None:
            self.parent._check_budgets(messages, system, max_tokens)

    # ---- public API -----------------------------------------------------------------

    async def complete(
        self,
        prompt: Prompt,
        *,
        system: str | None = None,
        max_tokens: int = 1024,
        temperature: float | None = 0.0,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Run a text completion.

        ``json_schema`` asks providers that support constrained decoding to emit JSON matching
        it; providers without that support ignore it.
        """
        messages = _normalize(prompt)
        self._check_budgets(messages, system, max_tokens)
        response = await self._with_retries(
            lambda: self._complete_raw(messages, system, max_tokens, temperature, json_schema)
        )
        cost = self.pricing.cost(response.input_tokens, response.output_tokens)
        response = response.model_copy(update={"cost_usd": cost})
        self._record(
            TokenUsage(
                llm_calls=1,
                input_tokens=response.input_tokens,
                output_tokens=response.output_tokens,
                cost_usd=cost,
            ),
            response.warnings,
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
        json_schema = schema.model_json_schema()
        instructions = (
            "Respond with a single JSON object that validates against this JSON Schema. "
            "Output only the JSON, with no prose and no code fences.\n"
            f"JSON Schema:\n{json.dumps(json_schema)}"
        )
        full_system = f"{system}\n\n{instructions}" if system else instructions
        messages = _normalize(prompt)
        last_error: Exception | None = None
        for _attempt in range(max_repair_attempts + 1):
            response = await self.complete(
                messages,
                system=full_system,
                max_tokens=max_tokens,
                temperature=temperature,
                json_schema=json_schema,
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
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        """Perform one provider call. Raise :class:`TransientLLMError` for retryable failures."""


class LLMSession(LLMClient):
    """A per-run view of a client: same provider and model, separate usage and budget.

    Provider calls are delegated to the parent client; retries and timeouts use the
    parent's settings.
    """

    provider: ClassVar[str] = "session"

    def __init__(self, parent: LLMClient, *, max_cost_usd: float | None = None) -> None:
        super().__init__(
            parent.model,
            max_cost_usd=max_cost_usd,
            timeout_s=parent.timeout_s,
            max_retries=parent.max_retries,
            backoff_base_s=parent.backoff_base_s,
            pricing=parent.pricing,
        )
        self.parent = parent

    @property
    def client(self) -> LLMClient:
        """The underlying provider client."""
        assert self.parent is not None
        return self.parent

    async def context_window(self) -> int | None:
        return await self.client.context_window()

    async def _complete_raw(
        self,
        messages: list[Message],
        system: str | None,
        max_tokens: int,
        temperature: float | None,
        json_schema: dict[str, Any] | None = None,
    ) -> LLMResponse:
        return await self.client._complete_raw(
            messages, system, max_tokens, temperature, json_schema
        )
