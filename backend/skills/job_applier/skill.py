"""The core Job Applier skill implementation."""
from __future__ import annotations

from typing import Any, TYPE_CHECKING

from skills.base import Skill
from tools.schemas import SkillResult
from .persona import PERSONA
from .workflow import run_job_apply_workflow

if TYPE_CHECKING:
    from agent.runner import BrowserAgent


class JobApplierSkill(Skill):
    @property
    def name(self) -> str:
        return "job_applier"

    @property
    def persona(self) -> str:
        return PERSONA

    @property
    def required_tool_categories(self) -> list[str]:
        # The agent loop only needs access to matching tools for the judgment step
        # The workflow itself calls the other tools directly in Python code.
        return ["matching"]

    async def run(self, task_config: dict[str, Any], agent: "BrowserAgent") -> SkillResult:
        """Delegate to the deterministic workflow pipeline."""
        return await run_job_apply_workflow(task_config, agent, self)
