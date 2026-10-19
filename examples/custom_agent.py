"""Example: Writing and executing a custom agent in Python.

Run directly with:
    uv run python examples/custom_agent.py
"""

from __future__ import annotations

import asyncio

from margin_core import (
    AgentInput,
    AgentRegistry,
    AgentResult,
    BaseAgent,
    Evidence,
    Finding,
    ProgressEvent,
    RunContext,
    run_agent,
)
from margin_core.llm import MockLLM
from margin_core.reporting import to_markdown
from pydantic import BaseModel, Field


# 1. Define structured Input and Output models
class WordCountInput(AgentInput):
    text: str = Field(description="The body of text to analyze.")
    target_word: str = Field(default="", description="Specific word to search for.")


class WordCountOutput(BaseModel):
    total_words: int
    char_count: int
    target_occurrences: int


# 2. Implement the BaseAgent interface
class WordCountAgent(BaseAgent):
    id = "word-counter"
    name = "Word Counter Agent"
    description = "Analyzes text length and counts word frequencies."
    version = "0.1.0"
    InputModel = WordCountInput
    OutputModel = WordCountOutput

    async def run(self, input: WordCountInput, ctx: RunContext) -> AgentResult:
        ctx.report_progress("analyze", "Counting words and characters...", fraction=0.3)

        words = input.text.split()
        total_words = len(words)
        char_count = len(input.text)
        occurrences = (
            sum(1 for w in words if w.lower() == input.target_word.lower())
            if input.target_word
            else 0
        )

        findings = []
        if input.target_word:
            findings.append(
                Finding(
                    title=f"Occurrences of '{input.target_word}'",
                    summary=f"Found '{input.target_word}' {occurrences} time(s).",
                    evidence=[
                        Evidence(
                            kind="metric",
                            detail=f"Word count frequency: {occurrences}/{total_words}",
                            weight=1.0 if occurrences > 0 else 0.0,
                        )
                    ],
                )
            )

        ctx.report_progress("done", "Analysis complete", fraction=1.0)

        return self.make_result(
            summary=f"Analyzed {total_words} words ({char_count} characters).",
            output=WordCountOutput(
                total_words=total_words,
                char_count=char_count,
                target_occurrences=occurrences,
            ),
            findings=findings,
        )


async def main() -> None:
    # 3. Create a registry and register our agent
    registry = AgentRegistry()
    registry.register(WordCountAgent)

    # 4. Define a progress listener
    def on_progress(event: ProgressEvent) -> None:
        print(f"[{event.stage.upper()}] {event.message} ({int((event.fraction or 0) * 100)}%)")

    # 5. Run the agent using run_agent
    ctx = RunContext(progress=on_progress, llm=MockLLM())
    result = await run_agent(
        "word-counter",
        {
            "text": (
                "AI agents are modular, focused, and structured. Every AI agent shares one core."
            ),
            "target_word": "AI",
        },
        ctx=ctx,
        registry=registry,
    )

    # 6. Render the report
    print("\n--- Agent Markdown Report ---")
    print(to_markdown(result))


if __name__ == "__main__":
    asyncio.run(main())
