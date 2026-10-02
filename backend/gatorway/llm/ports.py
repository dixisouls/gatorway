"""LLM-facing types. The orchestrator depends on LlmPort, never on the Gemini SDK directly."""
from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from gatorway.engine.models import Edit


class Intent(BaseModel):
    """What the student wants, extracted from free text."""

    specialization: bool = Field(description="True only if the text names a topic, skill, technology or career direction to focus electives on")
    topics: list[str] = Field(default_factory=list, description="Short topic phrases, e.g. 'web development'")
    keywords: list[str] = Field(default_factory=list, description="Technologies and skills, e.g. 'Next.js', 'React'")
    summary: str = Field(default="", description="One sentence restating the interest")

    def search_text(self) -> str:
        return " ".join(self.topics + self.keywords) or self.summary


class LlmPort(Protocol):
    async def parse_intent(self, interest: str) -> Intent: ...

    async def propose_edits(
        self, session_id: str, mcp: Any, allowed_tools: set[str], intent: Intent, feedback: list[str] | None
    ) -> list[Edit]: ...
