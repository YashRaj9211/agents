"""The complete model-driven browser-agent loop.

Skills will later be small prompts/specifications passed to this runner. Until
then, this runs a plain browser task so the foundation can be tested directly.
"""
from __future__ import annotations

import json
import uuid

from config import settings
from llm import LlmClient
from browser_mcp import PlaywrightMcpClient
from memory import Memory
from tools.local import LocalTools
from tools.registry import ToolRegistry

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from skills.base import Skill


SYSTEM_PROMPT = """You are an autonomous browser agent. You control a real web browser through
the provided Playwright MCP browser tools to complete the user's task. After navigation or a
meaningful page change, take a snapshot before interacting; use the element
references from that snapshot and never guess them. Work in small verifiable
steps. Never enter passwords, one-time codes, or personal details unless the
user has manually entered them in this browser session. Stop and explain if a
CAPTCHA, MFA challenge, payment, or irreversible submission requires the user.
Local file tools may only access storage/files. Read candidate documents from
input/ and write generated documents to output/. Do not claim a PDF was
created unless html_to_pdf reports success.
When the task is finished, reply with a short plain-text summary beginning
with DONE:. If you cannot continue, reply beginning with BLOCKED:."""


class BrowserAgent:
    def __init__(self, goal: str, skill: "Skill | None" = None) -> None:
        self.goal = goal
        self.skill = skill
        self.memory = Memory(uuid.uuid4().hex[:8])
        self.llm = LlmClient()
        self.browser = PlaywrightMcpClient()
        self.local_tools = LocalTools()
        self.registry = ToolRegistry()

    async def run(self) -> str:
        await self.browser.start()
        try:
            tools = await self.browser.openai_tools()
            tools.extend(self.local_tools.schemas)
            
            system_prompt = SYSTEM_PROMPT
            
            if self.skill:
                skill_tools = self.registry.subset(self.skill.required_tool_categories)
                tools.extend([t.schema for t in skill_tools])
                system_prompt += f"\n\nActive skill persona:\n{self.skill.persona}"
                
            self.memory.add({"role": "system", "content": system_prompt})
            self.memory.add({"role": "user", "content": self.goal})

            for _ in range(settings.max_steps):
                message = await self.llm.decide(self.memory.messages, tools)
                if not message.tool_calls:
                    answer = message.content or "BLOCKED: The model stopped without an explanation."
                    self.memory.add({"role": "assistant", "content": answer})
                    return answer

                self.memory.add({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [call.model_dump() for call in message.tool_calls],
                })
                for call in message.tool_calls:
                    try:
                        arguments = json.loads(call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                        
                    # 1. Try local tools
                    result = await self.local_tools.execute(call.function.name, arguments, self.browser)
                    
                    # 2. Try skill-registered tools
                    if result is None and self.skill:
                        tool_def = self.registry.get(call.function.name)
                        if tool_def and tool_def.category in self.skill.required_tool_categories:
                            import inspect
                            # Call the python function directly
                            if inspect.iscoroutinefunction(tool_def.callable_fn):
                                res = await tool_def.callable_fn(**arguments)
                            else:
                                res = tool_def.callable_fn(**arguments)
                            
                            if isinstance(res, str):
                                result = res
                            elif hasattr(res, "model_dump_json"):
                                result = res.model_dump_json()
                            else:
                                result = json.dumps(res)
                    
                    # 3. Fallback to browser tools
                    if result is None:
                        result = await self.browser.call_tool(call.function.name, arguments)
                        
                    self.memory.add({"role": "tool", "tool_call_id": call.id, "content": result})

            return f"BLOCKED: Reached the safety limit of {settings.max_steps} browser actions."
        finally:
            await self.browser.stop()

    async def run_generator(self):
        await self.browser.start()
        try:
            tools = await self.browser.openai_tools()
            tools.extend(self.local_tools.schemas)
            
            system_prompt = SYSTEM_PROMPT
            
            if self.skill:
                skill_tools = self.registry.subset(self.skill.required_tool_categories)
                tools.extend([t.schema for t in skill_tools])
                system_prompt += f"\n\nActive skill persona:\n{self.skill.persona}"
                
            self.memory.add({"role": "system", "content": system_prompt})
            self.memory.add({"role": "user", "content": self.goal})

            yield {"type": "info", "message": f"Starting task: {self.goal}"}

            for step in range(settings.max_steps):
                yield {"type": "step_start", "step": step + 1}
                message = await self.llm.decide(self.memory.messages, tools)
                
                if not message.tool_calls:
                    answer = message.content or "BLOCKED: The model stopped without an explanation."
                    self.memory.add({"role": "assistant", "content": answer})
                    yield {"type": "step_end", "step": step + 1, "result": answer}
                    yield {"type": "done", "result": answer}
                    return

                self.memory.add({
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [call.model_dump() for call in message.tool_calls],
                })
                
                for call in message.tool_calls:
                    try:
                        arguments = json.loads(call.function.arguments or "{}")
                    except json.JSONDecodeError:
                        arguments = {}
                        
                    yield {
                        "type": "tool_start",
                        "tool": call.function.name,
                        "arguments": arguments
                    }
                    
                    # 1. Try local tools
                    result = await self.local_tools.execute(call.function.name, arguments, self.browser)
                    
                    # 2. Try skill-registered tools
                    if result is None and self.skill:
                        tool_def = self.registry.get(call.function.name)
                        if tool_def and tool_def.category in self.skill.required_tool_categories:
                            import inspect
                            if inspect.iscoroutinefunction(tool_def.callable_fn):
                                res = await tool_def.callable_fn(**arguments)
                            else:
                                res = tool_def.callable_fn(**arguments)
                            
                            if isinstance(res, str):
                                result = res
                            elif hasattr(res, "model_dump_json"):
                                result = res.model_dump_json()
                            else:
                                result = json.dumps(res)
                    
                    # 3. Fallback to browser tools
                    if result is None:
                        result = await self.browser.call_tool(call.function.name, arguments)
                        
                    self.memory.add({"role": "tool", "tool_call_id": call.id, "content": result})
                    yield {
                        "type": "tool_end",
                        "tool": call.function.name,
                        "result": result
                    }
                
                yield {"type": "step_end", "step": step + 1, "result": message.content or "Tool execution completed."}

            blocked_msg = f"BLOCKED: Reached the safety limit of {settings.max_steps} browser actions."
            yield {"type": "blocked", "result": blocked_msg}
        finally:
            await self.browser.stop()

