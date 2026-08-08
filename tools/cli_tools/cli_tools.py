"""
CLI & PowerShell execution tools for ADK agents.

Lets an LlmAgent run shell commands, PowerShell scripts, and inspect results.
"""

import subprocess
import shlex
import os
import sys
from typing import Optional


# ---------------------------------------------------------------------------
# Run Shell Command
# ---------------------------------------------------------------------------

def run_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    env_vars: Optional[dict] = None,
) -> dict:
    """Execute a shell command and return its output.

    Args:
        command: The command string to execute (e.g. 'ls -la' or 'git status').
        cwd: Working directory for the command. Defaults to current directory.
        timeout: Maximum seconds to wait before killing the process (default 60).
        env_vars: Optional extra environment variables to inject (dict).

    Returns:
        A dict with keys:
            - 'stdout' (str): Standard output of the command.
            - 'stderr' (str): Standard error output.
            - 'returncode' (int): Process exit code (0 = success).
            - 'error' (str or None): Any Python-level exception message.
    """
    try:
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        result = subprocess.run(
            command,
            shell=True,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"Command timed out after {timeout} seconds",
        }
    except Exception as exc:
        return {"stdout": "", "stderr": "", "returncode": -1, "error": str(exc)}


# ---------------------------------------------------------------------------
# Run PowerShell Command / Script Block
# ---------------------------------------------------------------------------

def run_powershell(
    script: str,
    cwd: Optional[str] = None,
    timeout: int = 60,
    env_vars: Optional[dict] = None,
) -> dict:
    """Execute a PowerShell command or script block on Windows.

    Args:
        script: PowerShell command(s) or script block to run.
        cwd: Working directory. Defaults to current directory.
        timeout: Maximum seconds to wait (default 60).
        env_vars: Optional extra environment variables (dict).

    Returns:
        A dict with keys 'stdout', 'stderr', 'returncode', and 'error'.
    """
    try:
        env = os.environ.copy()
        if env_vars:
            env.update(env_vars)

        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", script,
        ]

        result = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
            env=env,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"PowerShell timed out after {timeout} seconds",
        }
    except FileNotFoundError:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": "PowerShell not found. Ensure powershell.exe is in PATH.",
        }
    except Exception as exc:
        return {"stdout": "", "stderr": "", "returncode": -1, "error": str(exc)}


# ---------------------------------------------------------------------------
# Run Python Script
# ---------------------------------------------------------------------------

def run_python_script(
    script_path: str,
    args: Optional[list] = None,
    cwd: Optional[str] = None,
    timeout: int = 120,
) -> dict:
    """Execute a Python script file using the current Python interpreter.

    Args:
        script_path: Path to the .py script file.
        args: Optional list of command-line arguments to pass to the script.
        cwd: Working directory. Defaults to current directory.
        timeout: Maximum seconds to wait (default 120).

    Returns:
        A dict with keys 'stdout', 'stderr', 'returncode', and 'error'.
    """
    try:
        cmd = [sys.executable, script_path] + (args or [])
        result = subprocess.run(
            cmd,
            cwd=cwd,
            timeout=timeout,
            capture_output=True,
            text=True,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": "",
            "returncode": -1,
            "error": f"Script timed out after {timeout} seconds",
        }
    except Exception as exc:
        return {"stdout": "", "stderr": "", "returncode": -1, "error": str(exc)}


# ---------------------------------------------------------------------------
# Convenience export list
# ---------------------------------------------------------------------------

CLI_TOOLS = [
    run_command,
    run_powershell,
    run_python_script,
]
