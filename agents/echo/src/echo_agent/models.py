"""Input and output models of the echo agent."""

from __future__ import annotations

from agents_core import AgentInput
from pydantic import BaseModel, Field


class EchoInput(AgentInput):
    message: str = Field(min_length=1, description="Text to echo back.")
    repeat: int = Field(default=1, ge=1, le=10, description="How many times to repeat it.")
    use_llm: bool = Field(default=False, description="Also send the message to the LLM.")


class EchoOutput(BaseModel):
    echoed: str
    length: int
    llm_reply: str | None = None
