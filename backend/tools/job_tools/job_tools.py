"""ADK tool functions for the job-hunt pipeline (scout -> matcher -> resume tailor)."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from tools.job_tools import job_store
from tools.job_tools.resume_renderer import TEMPLATES, render_resume_html


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
    return {"profile": job_store.save_profile(profile)}


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
    return job_store.add_jobs(jobs, source=source)


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
    return job_store.save_evaluations(evaluations)


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
    if not isinstance(resume, dict) or not resume.get("name"):
        return {"ok": False, "error": "resume must be a dict containing at least 'name'"}
    if template not in TEMPLATES:
        template = "modern"
    html = render_resume_html(resume, template=template, target=f'{job["title"]} @ {job["company"]}')
    job_store.save_resume_html(job_id, html, template, [str(n) for n in (change_notes or [])])
    return {"ok": True, "job_id": job_id, "template": template, "bytes": len(html.encode("utf-8")),
            "preview_url": f"/api/jobhunt/jobs/{job_id}/resume"}


JOB_SCOUT_TOOLS = [get_candidate_profile, save_candidate_profile, save_scraped_jobs]
JOB_MATCHER_TOOLS = [get_candidate_profile, list_jobs_to_evaluate, save_job_evaluations, get_top_jobs]
RESUME_TAILOR_TOOLS = [get_candidate_profile, get_top_jobs, get_job_details, build_tailored_resume]
