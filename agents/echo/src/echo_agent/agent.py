"""Echo agent: the smallest complete example of the agent contract."""

from __future__ import annotations

from agents_core import AgentInput, AgentResult, BaseAgent, Evidence, Finding, RunContext
from pydantic import BaseModel, Field


class EchoInput(AgentInput):
    message: str = Field(min_length=1, description="Text to echo back.")
    repeat: int = Field(default=1, ge=1, le=10, description="How many times to repeat it.")
    use_llm: bool = Field(default=False, description="Also send the message to the LLM.")


class EchoOutput(BaseModel):
    echoed: str
    length: int
    llm_reply: str | None = None


class EchoAgent(BaseAgent):
    id = "echo"
    name = "Echo Agent"
    description = "Echoes its input back. Useful for smoke-testing the toolchain."
    version = "0.1.0"
    InputModel = EchoInput
    OutputModel = EchoOutput

    async def run(self, input: EchoInput, ctx: RunContext) -> AgentResult:
        ctx.report_progress("echo", "Echoing message", 0.0)
        echoed = " ".join([input.message] * input.repeat)

        llm_reply: str | None = None
        if input.use_llm:
            ctx.check_cancelled()
            ctx.report_progress("llm", "Asking the LLM", 0.5)
            llm_reply = (await ctx.require_llm().complete(input.message)).text

        ctx.report_progress("done", "Finished", 1.0)
        return self.make_result(
            summary=f"Echoed {len(echoed)} characters ({input.repeat}x).",
            output=EchoOutput(echoed=echoed, length=len(echoed), llm_reply=llm_reply),
            findings=[
                Finding(
                    title="Echo",
                    summary=echoed,
                    evidence=[Evidence(kind="metric", detail=f"length={len(echoed)}")],
                )
            ],
        )
