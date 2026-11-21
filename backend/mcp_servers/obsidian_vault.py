"""
obsidian_vault.py
-----------------
MCPVault toolset factory: gives agents long-term memory in an Obsidian vault.

MCPVault (https://github.com/bitbonsai/mcpvault) is a local stdio MCP server that
reads/writes the vault folder directly. Obsidian does NOT need to be running and no
plugin is required. Open the same folder in Obsidian to browse the graph live.

Config (env):
    OBSIDIAN_VAULT_PATH   Vault folder. Default: <repo>/data/vault (gitignored).

Usage:
    from mcp_servers.obsidian_vault import get_vault_toolset
    tools = [get_vault_toolset()]                  # read + write (root agent)
    tools = [get_vault_toolset(read_only=True)]    # search/read only

Memory rules live in docs/memory-protocol.md and are mirrored in the root agent prompt.
"""

from __future__ import annotations

import os
from pathlib import Path

from google.adk.tools.mcp_tool import McpToolset, StdioConnectionParams
from mcp import StdioServerParameters

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_VAULT = _PROJECT_ROOT / "data" / "vault"

# Pinned so a surprise upstream release can't change tool behaviour under the agents.
MCPVAULT_PACKAGE = "@bitbonsai/mcpvault@0.18.4"


def get_vault_path() -> Path:
    """Resolves the vault folder and makes sure it exists."""
    path = Path(os.getenv("OBSIDIAN_VAULT_PATH") or _DEFAULT_VAULT).expanduser().resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def create_vault_toolset(
    read_only: bool = False,
    exclude: list[str] | None = None,
    timeout: float = 60.0,
) -> McpToolset:
    """
    Creates an ADK McpToolset connected to MCPVault.

    Args:
        read_only: Hide/reject every mutating tool (use for untrusted agents).
        exclude:   Vault-relative folders hidden from search/list for this toolset.
        timeout:   Connection timeout in seconds.
    """
    args = ["-y", MCPVAULT_PACKAGE, str(get_vault_path())]
    if read_only:
        args.append("--read-only")
    for folder in exclude or []:
        args += ["--exclude", folder]

    server_params = StdioServerParameters(
        command="npx",
        args=args,
        env=os.environ.copy(),
    )
    return McpToolset(
        connection_params=StdioConnectionParams(server_params=server_params, timeout=timeout),
    )


def get_vault_toolset(read_only: bool = False, exclude: list[str] | None = None) -> McpToolset:
    """Returns a fresh toolset (one MCP subprocess per agent keeps permissions separate)."""
    return create_vault_toolset(read_only=read_only, exclude=exclude)
