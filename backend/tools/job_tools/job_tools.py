"""ADK tool functions for the job-hunt pipeline (scout -> matcher -> resume tailor)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from tools.job_tools import job_store
from tools.job_tools.resume_renderer import TEMPLATES, render_resume_html


def _coerce(value: Any, kind: type) -> Any:
    """LLMs sometimes pass structured args as a JSON string; decode it so tools don't crash."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return None
    if kind is list and isinstance(value, dict):
        value = [value]
    return value if isinstance(value, kind) else None


def get_candidate_profile() -> dict:
    """Return the saved candidate profile (resume facts, target roles, preferences).

    Returns:
        dict with 'profile' (empty dict if none saved yet).
    """
    profile = job_store.get_profile()
    if profile.get("sample"):  # dashboard preview data must never leak into real runs
        profile = {}
    return {"profile": profile}


def save_candidate_profile(profile: Dict[str, Any]) -> dict:
    """Save or update the candidate profile used to search, rank and tailor resumes.

    Args:
        profile: Dict. Recommended keys: name, headline, contact {email, phone, location, links[{label,url}]},
            summary, target_roles [str], locations [str], work_mode, min_salary, years_experience,
            skills [{category, items[str]}], experience [{company,title,location,dates,bullets[str]}],
            projects [{title,stack,link,bullets[str]}], education [{institution,degree,dates,details}],
            additional [{category,text}], dealbreakers [str]. Existing keys not provided are kept.

    Returns:
        dict with the merged 'profile'.
    """
    data = _coerce(profile, dict)
    if data is None:
        return {"ok": False, "error": "profile must be a JSON object (dict), not plain text"}
    return {"profile": job_store.save_profile(data)}


def save_scraped_jobs(jobs: List[Dict[str, Any]], source: str = "") -> dict:
    """Save job postings found while browsing. Duplicates (same URL) are merged automatically.

    Call this after EACH page/batch of results (every 10-20 jobs) so nothing is lost if the run stops.
    Only save postings you actually saw; never invent fields. Leave a field empty if unknown.

    Args:
        jobs: List of dicts with keys: title, company, location, url, salary, posted, work_mode
            (remote/hybrid/onsite), experience_level, skills [str], description (the real posting text,
            responsibilities + requirements, up to ~2000 chars). 'title' and 'company' are required.
        source: Site name, e.g. 'LinkedIn', 'Naukri', 'Wellfound'.

    Returns:
        dict with added, duplicates_merged, skipped_invalid, total_jobs.
    """
    items = _coerce(jobs, list)
    if items is None:
        return {"ok": False, "error": "jobs must be a list of job objects"}
    return job_store.add_jobs(items, source=source)


def list_jobs_to_evaluate(limit: int = 10) -> dict:
    """Return scraped jobs that have no evaluation yet (batch of at most `limit`).

    Args:
        limit: Batch size, 1-25. Evaluate in batches then call this again until 'remaining' is 0.

    Returns:
        dict with 'jobs' (id, title, company, location, work_mode, salary, experience_level, skills,
        description) and 'remaining' (how many unevaluated jobs are left after this batch).
    """
    limit = max(1, min(25, int(limit)))
    pending = job_store.list_jobs(evaluated=False)
    batch = [
        {k: j.get(k) for k in ("id", "title", "company", "location", "work_mode", "salary",
                                "experience_level", "skills", "description", "url")}
        for j in pending[:limit]
    ]
    return {"jobs": batch, "remaining": max(0, len(pending) - len(batch))}


def save_job_evaluations(evaluations: List[Dict[str, Any]]) -> dict:
    """Save match evaluations. The overall score and verdict are computed for you from the parameters.

    Args:
        evaluations: List of dicts, one per job:
          {
            "job_id": "<id from list_jobs_to_evaluate>",
            "parameters": {  # every key required, score 0-100 and a one-line concrete note
               "skills":       {"score": 85, "note": "Python, FastAPI, Postgres match; no Kafka"},
               "experience":   {"score": 70, "note": "Asks 3-5 yrs, candidate has 2.5"},
               "role_fit":     {"score": 90, "note": "Backend-heavy, matches target roles"},
               "location":     {"score": 100, "note": "Remote"},
               "compensation": {"score": 60, "note": "Salary not listed"},
               "growth":       {"score": 75, "note": "..."},
               "company":      {"score": 70, "note": "..."}
            },
            "why":  ["2-4 specific reasons this job suits the candidate"],
            "gaps": ["requirements the candidate is missing"],
            "red_flags": ["e.g. unpaid trial, vague JD, below target salary"]
          }

    Returns:
        dict with saved count and any unknown_job_ids.
    """
    items = _coerce(evaluations, list)
    if items is None:
        return {"ok": False, "error": "evaluations must be a list of evaluation objects"}
    return job_store.save_evaluations(items)


def get_top_jobs(limit: int = 10, min_score: int = 65) -> dict:
    """Return the best evaluated jobs (highest overall score first).

    Args:
        limit: Max jobs to return.
        min_score: Minimum overall score 0-100.

    Returns:
        dict with 'jobs' including id, title, company, overall, verdict, why, gaps, has_resume.
    """
    jobs = [j for j in job_store.list_jobs(evaluated=True) if j["evaluation"]["overall"] >= min_score][: max(1, limit)]
    return {"jobs": [
        {"id": j["id"], "title": j["title"], "company": j["company"], "overall": j["evaluation"]["overall"],
         "verdict": j["evaluation"]["verdict"], "why": j["evaluation"]["why"], "gaps": j["evaluation"]["gaps"],
         "has_resume": bool(j.get("resume"))}
        for j in jobs
    ]}


def get_job_details(job_id: str) -> dict:
    """Return the full record for one job (posting text, evaluation, resume status).

    Args:
        job_id: Id of the job.

    Returns:
        dict with 'job' or 'error'.
    """
    job = job_store.get_job(job_id)
    return {"job": job} if job else {"error": f"No job with id {job_id}"}


def _words(value) -> int:
    if isinstance(value, str):
        return len(value.split())
    if isinstance(value, dict):
        return sum(_words(v) for v in value.values())
    if isinstance(value, list):
        return sum(_words(v) for v in value)
    return 0


def _density_problem(resume: Dict[str, Any]) -> Optional[str]:
    """The resume must fill ONE A4 page (~95%+): reject content that is too thin or too long."""
    bullets = sum(len(x.get("bullets") or []) for k in ("experience", "projects")
                  for x in (resume.get(k) or []) if isinstance(x, dict))
    words = _words({k: v for k, v in resume.items() if k not in ("name", "contact")})
    if words < 330 or bullets < 10:
        return (f"Resume is too thin to fill a full page ({words} words, {bullets} bullets; need >= 330 words "
                f"and >= 10 bullets). Re-read the vault profile (profile/Yash-Job-Profile.md) and include EVERY "
                f"relevant role, project, skill group, certification and achievement, with 3-4 bullets per role/project.")
    if words > 650 or bullets > 20:
        return (f"Resume is too long for one page ({words} words, {bullets} bullets; max 650 words / 20 bullets). "
                f"Tighten wording and drop the least relevant bullets.")
    return None


def build_tailored_resume(job_id: str, resume: Dict[str, Any], template: str = "modern",
                          change_notes: Optional[List[str]] = None) -> dict:
    """Render a tailored resume for a job as ONE self-contained HTML+CSS file and save it.

    Truthfulness rule: use ONLY facts from the candidate profile. Re-order, re-word and emphasise
    to match the job's keywords, but never invent employers, titles, dates, metrics or skills.

    Args:
        job_id: Id of the job this resume targets.
        resume: Dict with name, headline (retitled for this role), contact {email, phone, location,
            links[{label,url}]}, summary (2-3 lines aimed at this job), skills [{category, items[str]}]
            (job-relevant first), experience [{company,title,location,dates,bullets[str]}],
            projects [{title,stack,link,bullets[str]}], education [{institution,degree,dates,details}],
            additional [{category,text}].
        template: 'modern' (two-column, visual) or 'classic' (single-column, ATS-safe).
        change_notes: Short bullets describing what was tailored and why (shown in the UI).

    Returns:
        dict with ok, job_id, template, bytes, preview_url (relative API path).
    """
    job = job_store.get_job(job_id)
    if not job:
        return {"ok": False, "error": f"No job with id {job_id}"}
    resume = _coerce(resume, dict)
    if not resume or not resume.get("name"):
        return {"ok": False, "error": "resume must be a dict containing at least 'name'"}
    if template not in TEMPLATES:
        template = "modern"
    problem = _density_problem(resume)
    if problem:
        return {"ok": False, "error": problem}
    html = render_resume_html(resume, template=template, target=f'{job["title"]} @ {job["company"]}')
    job_store.save_resume_html(job_id, html, template, [str(n) for n in (change_notes or [])])
    result = {"ok": True, "job_id": job_id, "template": template, "bytes": len(html.encode("utf-8")),
              "preview_url": f"/api/jobhunt/jobs/{job_id}/resume"}
    # Also register the resume in the Artifacts tab (Garage S3 + DB); best-effort, the local copy is the source of truth.
    try:
        from app.services.storage_service import store_agent_artifact_sync
        safe = "".join(c if c.isalnum() else "_" for c in f'{job["company"]}_{job["title"]}')[:80]
        art = store_agent_artifact_sync(
            name=f"Resume_{safe}_{job_id}.html", content=html, kind="document", mime_type="text/html",
            metadata={"job_id": job_id, "template": template, "source": "job_hunt"})
        result["artifact_id"] = art.get("id")
    except Exception as e:  # noqa: BLE001
        result["artifact_warning"] = f"Saved locally but not added to Artifacts: {e}"
    return result


JOB_SCOUT_TOOLS = [get_candidate_profile, save_candidate_profile, save_scraped_jobs]
JOB_MATCHER_TOOLS = [get_candidate_profile, list_jobs_to_evaluate, save_job_evaluations, get_top_jobs]
RESUME_TAILOR_TOOLS = [get_candidate_profile, get_top_jobs, get_job_details, build_tailored_resume]
