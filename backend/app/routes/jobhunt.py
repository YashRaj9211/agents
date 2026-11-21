"""Job Hunt API: profile, ranked jobs, tailored single-file HTML resumes."""
from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from tools.job_tools import job_store
from tools.job_tools.sample_data import load_sample_jobs

router = APIRouter(prefix="/jobhunt", tags=["Job Hunt"])


class StatusBody(BaseModel):
    status: str


@router.get("/overview")
async def overview() -> Dict[str, Any]:
    return {"stats": job_store.stats(), "profile": job_store.get_profile(), "weights": job_store.PARAMETER_WEIGHTS}


@router.get("/profile")
async def get_profile() -> Dict[str, Any]:
    return job_store.get_profile()


@router.put("/profile")
async def put_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    return job_store.save_profile(profile)


@router.get("/jobs")
async def list_jobs(
    status: Optional[str] = Query(None),
    evaluated: Optional[bool] = Query(None),
) -> Dict[str, Any]:
    jobs = job_store.list_jobs(status=status, evaluated=evaluated)
    for j in jobs:
        j["has_resume"] = bool(j.get("resume"))
    return {"jobs": jobs, "stats": job_store.stats()}


@router.get("/jobs/{job_id}")
async def get_job(job_id: str) -> Dict[str, Any]:
    job = job_store.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.patch("/jobs/{job_id}/status")
async def set_status(job_id: str, body: StatusBody) -> Dict[str, Any]:
    try:
        job = job_store.set_status(job_id, body.status)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if not job:
        raise HTTPException(404, "Job not found")
    return job


@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str) -> Dict[str, Any]:
    if not job_store.delete_job(job_id):
        raise HTTPException(404, "Job not found")
    return {"deleted": job_id}


@router.get("/jobs/{job_id}/resume", response_class=HTMLResponse)
async def view_resume(job_id: str, download: bool = False) -> Response:
    html = job_store.read_resume_html(job_id)
    if html is None:
        raise HTTPException(404, "No tailored resume for this job yet")
    headers = {"Content-Disposition": f'attachment; filename="resume-{job_id}.html"'} if download else {}
    return HTMLResponse(html, headers=headers)


@router.post("/sample")
async def add_sample() -> Dict[str, Any]:
    """Load clearly-labelled SAMPLE jobs (source='sample') so the dashboard can be previewed without running agents."""
    return load_sample_jobs()


@router.delete("/sample")
async def clear_sample() -> Dict[str, Any]:
    return {"removed": job_store.clear_jobs(sample_only=True)}
