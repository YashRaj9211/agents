"""Abstract base class for all skills."""
from __future__ import annotations

import abc
from typing import Any, TYPE_CHECKING

from tools.schemas import SkillResult

if TYPE_CHECKING:
    from agent.runner import BrowserAgent


class Skill(abc.ABC):
    """
    A skill is a workflow that coordinates deterministic tools and LLM steps.
    It declares which tool categories it needs from the registry.
    """

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Name of the skill."""
        pass

    @property
    @abc.abstractmethod
    def persona(self) -> str:
        """The system prompt / persona for this skill."""
        pass

    @property
    @abc.abstractmethod
    def required_tool_categories(self) -> list[str]:
        """Which categories of tools this skill injects into the LLM context."""
        pass

    @abc.abstractmethod
    async def run(self, task_config: dict[str, Any], agent: "BrowserAgent") -> SkillResult:
        """
        Execute the skill workflow.
        Deterministic steps call tools directly.
        Judgment steps hand off to the agent's LLM context.
        """
        pass
