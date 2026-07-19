"""FastAPI app for running browser automation with SSE streaming."""
from __future__ import annotations

import asyncio
import json
import uuid
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent.runner import BrowserAgent

app = FastAPI(title="Web Automation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store running tasks: task_id -> asyncio.Task
active_tasks: dict[str, asyncio.Task] = {}

class RunRequest(BaseModel):
    goal: str

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}

@app.get("/api/run")
async def run_agent(goal: str, request: Request):
    task_id = str(uuid.uuid4())
    current_task = asyncio.current_task()
    active_tasks[task_id] = current_task
    
    agent = BrowserAgent(goal)
    
    async def event_generator():
        # First yield the started event with the task_id
        yield {
            "event": "message",
            "data": json.dumps({"type": "started", "task_id": task_id})
        }
        try:
            async for event in agent.run_generator():
                yield {
                    "event": "message",
                    "data": json.dumps(event)
                }
        except asyncio.CancelledError:
            yield {
                "event": "message",
                "data": json.dumps({"type": "info", "message": "Agent execution stopped by user."})
            }
            raise
        except Exception as e:
            yield {
                "event": "message",
                "data": json.dumps({"type": "error", "message": str(e)})
            }
        finally:
            active_tasks.pop(task_id, None)
            
    return EventSourceResponse(event_generator())

@app.post("/api/stop")
async def stop_agent(task_id: str):
    task = active_tasks.get(task_id)
    if not task:
        return {"status": "error", "message": f"No active agent task found with ID: {task_id}"}
    
    task.cancel()
    return {"status": "success", "message": f"Agent task {task_id} cancellation requested."}

