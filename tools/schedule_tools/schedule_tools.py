"""
Cron / Scheduling tools for ADK agents.

Uses the 'schedule' library for lightweight in-process recurring jobs,
and the Windows Task Scheduler (schtasks) for persistent OS-level cron jobs.
"""

import subprocess
import threading
import time as _time
from typing import Callable, Optional
import json

# In-memory registry of running schedule threads
_schedule_registry: dict[str, threading.Thread] = {}


# ---------------------------------------------------------------------------
# List Windows Scheduled Tasks
# ---------------------------------------------------------------------------

def list_scheduled_tasks(task_name_filter: Optional[str] = None) -> dict:
    """List Windows Scheduled Tasks using schtasks.

    Args:
        task_name_filter: Optional substring to filter task names.

    Returns:
        A dict with keys 'tasks' (list of task info dicts) and 'error' (str or None).
    """
    try:
        cmd = 'schtasks /Query /FO CSV /NH'
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            return {"tasks": [], "error": result.stderr.strip()}

        tasks = []
        for line in result.stdout.strip().splitlines():
            parts = [p.strip('"') for p in line.split('","')]
            if len(parts) >= 3:
                task = {"name": parts[0], "next_run": parts[1], "status": parts[2]}
                if task_name_filter is None or task_name_filter.lower() in task["name"].lower():
                    tasks.append(task)

        return {"tasks": tasks, "error": None}
    except Exception as exc:
        return {"tasks": [], "error": str(exc)}


# ---------------------------------------------------------------------------
# Create Windows Scheduled Task
# ---------------------------------------------------------------------------

def create_scheduled_task(
    task_name: str,
    command: str,
    schedule_type: str = "DAILY",
    start_time: str = "09:00",
    interval_minutes: Optional[int] = None,
    start_date: Optional[str] = None,
) -> dict:
    """Create a persistent Windows Scheduled Task using schtasks.

    Args:
        task_name: Unique name for the task (e.g. 'MyAgentTask').
        command: The command/program to run (e.g. 'python C:\\scripts\\job.py').
        schedule_type: One of MINUTE, HOURLY, DAILY, WEEKLY, MONTHLY, ONCE.
        start_time: Start time in HH:MM 24-hour format (default '09:00').
        interval_minutes: For MINUTE schedule – run every N minutes.
        start_date: Start date in MM/DD/YYYY format (optional).

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        cmd_parts = [
            "schtasks", "/Create", "/F",
            "/TN", task_name,
            "/TR", command,
            "/SC", schedule_type.upper(),
            "/ST", start_time,
        ]
        if interval_minutes is not None:
            cmd_parts += ["/MO", str(interval_minutes)]
        if start_date:
            cmd_parts += ["/SD", start_date]

        result = subprocess.run(
            cmd_parts, capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Delete Windows Scheduled Task
# ---------------------------------------------------------------------------

def delete_scheduled_task(task_name: str) -> dict:
    """Delete a Windows Scheduled Task by name.

    Args:
        task_name: The exact name of the task to delete.

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        result = subprocess.run(
            ["schtasks", "/Delete", "/F", "/TN", task_name],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Run Windows Scheduled Task Now
# ---------------------------------------------------------------------------

def run_scheduled_task_now(task_name: str) -> dict:
    """Immediately trigger a Windows Scheduled Task.

    Args:
        task_name: The exact name of the task to run.

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    try:
        result = subprocess.run(
            ["schtasks", "/Run", "/TN", task_name],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip() or result.stdout.strip()}
        return {"success": True, "error": None}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# Schedule In-Process Recurring Command (lightweight, non-persistent)
# ---------------------------------------------------------------------------

def schedule_recurring_command(
    job_id: str,
    command: str,
    interval_seconds: int,
    cwd: Optional[str] = None,
) -> dict:
    """Schedule a shell command to run repeatedly in-process (non-persistent).

    Starts a background thread that runs the command every interval_seconds.
    This is NOT persistent—it stops when the process exits.
    For persistent jobs, use create_scheduled_task() instead.

    Args:
        job_id: Unique identifier for this job (used to cancel it later).
        command: Shell command to run.
        interval_seconds: How often to run the command (in seconds).
        cwd: Working directory for the command.

    Returns:
        A dict with keys 'success' (bool), 'job_id' (str), and 'error' (str or None).
    """
    if job_id in _schedule_registry and _schedule_registry[job_id].is_alive():
        return {"success": False, "job_id": job_id, "error": f"Job '{job_id}' is already running"}

    stop_event = threading.Event()

    def _runner():
        while not stop_event.wait(interval_seconds):
            subprocess.run(command, shell=True, cwd=cwd)

    thread = threading.Thread(target=_runner, name=f"schedule-{job_id}", daemon=True)
    thread.stop_event = stop_event  # type: ignore[attr-defined]
    thread.start()
    _schedule_registry[job_id] = thread

    return {"success": True, "job_id": job_id, "error": None}


# ---------------------------------------------------------------------------
# Cancel In-Process Recurring Command
# ---------------------------------------------------------------------------

def cancel_recurring_command(job_id: str) -> dict:
    """Cancel a running in-process scheduled command by its job_id.

    Args:
        job_id: The job_id used when calling schedule_recurring_command.

    Returns:
        A dict with keys 'success' (bool) and 'error' (str or None).
    """
    thread = _schedule_registry.get(job_id)
    if thread is None:
        return {"success": False, "error": f"No job found with id '{job_id}'"}
    if not thread.is_alive():
        _schedule_registry.pop(job_id, None)
        return {"success": True, "error": None}

    thread.stop_event.set()  # type: ignore[attr-defined]
    thread.join(timeout=5)
    _schedule_registry.pop(job_id, None)
    return {"success": True, "error": None}


# ---------------------------------------------------------------------------
# List Active In-Process Jobs
# ---------------------------------------------------------------------------

def list_active_jobs() -> dict:
    """List all currently active in-process scheduled jobs.

    Returns:
        A dict with key 'jobs' (list of job_id strings that are still running).
    """
    active = [jid for jid, t in _schedule_registry.items() if t.is_alive()]
    return {"jobs": active, "error": None}


# ---------------------------------------------------------------------------
# Convenience export list
# ---------------------------------------------------------------------------

SCHEDULE_TOOLS = [
    list_scheduled_tasks,
    create_scheduled_task,
    delete_scheduled_task,
    run_scheduled_task_now,
    schedule_recurring_command,
    cancel_recurring_command,
    list_active_jobs,
]
