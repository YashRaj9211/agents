"""Tool registry to discover and provide tool subsets to skills."""
from __future__ import annotations

import importlib
import inspect
import logging
import pkgutil
from dataclasses import dataclass
from typing import Any, Callable

log = logging.getLogger("tools.registry")


@dataclass
class ToolDefinition:
    name: str
    callable_fn: Callable[..., Any]
    schema: dict[str, Any]
    category: str


class ToolRegistry:
    """Discovers and vends tools for LLM agent loops."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}
        self._discover_tools()

    def _discover_tools(self) -> None:
        """Scan tools/ subpackages for modules exporting SCHEMA, CATEGORY, and a function."""
        import tools

        for loader, name, is_pkg in pkgutil.walk_packages(tools.__path__, tools.__name__ + "."):
            if is_pkg:
                continue
            
            try:
                module = importlib.import_module(name)
            except Exception as e:
                log.warning("Failed to import %s: %s", name, e)
                continue

            if hasattr(module, "SCHEMA") and hasattr(module, "CATEGORY"):
                schema = getattr(module, "SCHEMA")
                category = getattr(module, "CATEGORY")
                tool_name = schema.get("function", {}).get("name")
                
                if not tool_name:
                    log.warning("Tool schema in %s missing function name", name)
                    continue

                # The callable should have the same name as the tool
                callable_fn = getattr(module, tool_name, None)
                if not callable_fn or not callable(callable_fn):
                    log.warning("Module %s does not export a callable named %s", name, tool_name)
                    continue

                self._tools[tool_name] = ToolDefinition(
                    name=tool_name,
                    callable_fn=callable_fn,
                    schema=schema,
                    category=category,
                )
                log.debug("Registered tool %s (category: %s) from %s", tool_name, category, name)

    def get(self, name: str) -> ToolDefinition | None:
        """Get a specific tool definition by name."""
        return self._tools.get(name)

    def subset(self, categories: list[str]) -> list[ToolDefinition]:
        """Return all tools belonging to the specified categories."""
        return [t for t in self._tools.values() if t.category in categories]

    def openai_schemas(self, categories: list[str] | None = None) -> list[dict[str, Any]]:
        """Return the OpenAI-format schemas for tools, optionally filtered by category."""
        tools = self.subset(categories) if categories else self._tools.values()
        return [t.schema for t in tools]
