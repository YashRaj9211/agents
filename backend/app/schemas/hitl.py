"""Human-in-the-loop schemas: question payloads and answer submissions."""
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class HumanInputOption(BaseModel):
    """One selectable answer. ``value`` is what gets posted back, ``label`` is UI text."""

    label: str
    value: str
    description: Optional[str] = None


class HumanInputItem(BaseModel):
    """An outstanding question the agent is blocked on."""

    question_id: str
    session_id: Optional[str] = None
    run_id: Optional[str] = None
    agent_id: Optional[str] = None
    kind: str = "confirm"
    question: str
    options: List[HumanInputOption] = Field(default_factory=list)
    created_at: Optional[float] = None


class PendingHumanInputResponse(BaseModel):
    session_id: str
    total: int = 0
    questions: List[HumanInputItem] = Field(default_factory=list)


class HumanInputAnswer(BaseModel):
    """Body of ``POST /api/hitl/{question_id}/answer``.

    ``answer`` is intentionally loose: a bool for confirmations, a value for a
    single choice, a list of values for a multi-select, or free text.
    """

    answer: Any = Field(default=None, description="bool | str | list[str]")


class HumanInputAnswerResponse(BaseModel):
    status: str
    question_id: str
    answered: bool
    answer: Optional[str] = None
    message: Optional[str] = None
