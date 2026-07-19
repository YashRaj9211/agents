"""Run the browser agent from the command line."""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import yaml
import json

from agent import BrowserAgent
from skills.job_applier import JobApplierSkill


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a browser automation task.")
    parser.add_argument("goal", nargs="?", help="What should the browser agent do? (Optional if --task is provided)")
    parser.add_argument("--skill", choices=["job_search", "job_apply"], help="Legacy text-prompt skill selector.")
    parser.add_argument("--task", help="Path to a YAML task config to run via a Python Skill.")
    args = parser.parse_args()

    if args.task:
        # New pattern: run a Python Skill workflow
        task_path = Path(args.task)
        if not task_path.exists():
            print(f"Task file not found: {task_path}")
            return
            
        with task_path.open("r", encoding="utf-8") as f:
            task_config = yaml.safe_load(f)
            
        skill = JobApplierSkill()
        agent = BrowserAgent("Run job applier workflow", skill=skill)
        
        print(f"\n=== Starting Skill: {skill.name} ===")
        # The agent isn't running its own loop for the deterministic skill, 
        # but we need to start its browser before the skill can use it.
        async def run_skill():
            await agent.browser.start()
            try:
                result = await skill.run(task_config, agent)
                print("\n=== SKILL RESULT ===")
                print(json.dumps(result.model_dump(), indent=2))
            finally:
                await agent.browser.stop()
                
        asyncio.run(run_skill())
        return

    # Legacy pattern
    if not args.goal:
        print("Error: goal is required when --task is not provided.")
        return
        
    skill_instructions = ""
    if args.skill:
        skill_path = Path(__file__).parent / "skills" / f"{args.skill}.md"
        if skill_path.exists():
            skill_instructions = skill_path.read_text(encoding="utf-8")
            
    # For legacy pattern, we pass skill_instructions via a dummy object or handle in runner
    # Since we refactored runner to take a Skill object, we can stub it:
    class LegacySkill:
        name = args.skill or "legacy"
        persona = skill_instructions
        required_tool_categories = []
        
        async def run(self, *args, **kwargs):
            pass
            
    agent = BrowserAgent(args.goal, skill=LegacySkill() if skill_instructions else None)
    result = asyncio.run(agent.run())
    
    print("\n=== RESULT ===")
    print(result)


if __name__ == "__main__":
    main()
