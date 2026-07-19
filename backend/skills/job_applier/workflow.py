"""Deterministic 10-step workflow for applying to jobs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TYPE_CHECKING

import yaml

from tools.resume.parse import parse_resume
from tools.resume.analyze import analyze_resume
from tools.web.search_jobs import search_jobs
from tools.web.get_job_details import get_job_details
from tools.web.fill_form import fill_application
from tools.web.upload_file import upload_file
from tools.web.submit import submit_application
from tools.matching.keyword_score import keyword_score
from tools.matching.llm_score import score_job_match
from tools.generation.cover_letter import generate_cover_letter
from tools.storage.job_tracker import job_tracker
from tools.storage.rate_limiter import throttle
from tools.schemas import SkillResult, SkillStatus

if TYPE_CHECKING:
    from agent.runner import BrowserAgent
    from skills.job_applier.skill import JobApplierSkill


def _load_config() -> dict[str, Any]:
    config_path = Path(__file__).parent / "config.yaml"
    if not config_path.exists():
        return {"dry_run": True, "match_threshold": 70, "sites": []}
    with config_path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f)


async def run_job_apply_workflow(
    task_config: dict[str, Any], 
    agent: "BrowserAgent",
    skill: "JobApplierSkill"
) -> SkillResult:
    """The 10-step deterministic sequence."""
    skill_config = _load_config()
    dry_run = task_config.get("dry_run", skill_config.get("dry_run", True))
    threshold = skill_config.get("match_threshold", 70)
    sites = task_config.get("sites", skill_config.get("sites", []))
    queries = task_config.get("target_roles", [])
    locations = task_config.get("locations", ["Remote"])
    resume_path = task_config.get("resume_path")

    if not resume_path or not Path(resume_path).is_file():
        return SkillResult(
            status=SkillStatus.FAILED, 
            summary="Resume file not found.",
            errors=[f"Invalid resume path: {resume_path}"]
        )

    # 1. Parse resume
    raw_resume = parse_resume(resume_path)
    if "Error" in raw_resume:
        return SkillResult(status=SkillStatus.FAILED, summary="Failed to parse resume.", errors=[raw_resume])

    # 2. Analyze resume (LLM)
    try:
        profile = await analyze_resume(raw_resume)
    except Exception as e:
        return SkillResult(status=SkillStatus.FAILED, summary="Failed to analyze resume.", errors=[str(e)])

    jobs_processed = 0
    jobs_applied = 0
    errors = []

    for site in sites:
        for query in queries:
            for location in locations:
                await throttle(site)
                
                # 3. Search jobs
                search_res = await search_jobs(agent.browser, query, location, site)
                try:
                    jobs_found = json.loads(search_res)
                    if isinstance(jobs_found, dict) and "error" in jobs_found:
                        errors.append(jobs_found["error"])
                        continue
                except json.JSONDecodeError:
                    errors.append(f"Invalid search response from {site}")
                    continue

                for job in jobs_found:
                    job_url = job["url"]
                    jobs_processed += 1
                    
                    # 4. Fast keyword filter
                    kw_score = keyword_score(profile.skills, job.get("description", "") + " " + " ".join(job.get("requirements", [])))
                    if kw_score < 0.1: # Very low bar to discard complete mismatches early
                        job_tracker("save_job", job_id=job_url, company=job["company"], url=job_url, status="rejected_keyword", match_score=int(kw_score*100))
                        continue

                    # 5. Get full details
                    await throttle(site)
                    details = await get_job_details(agent.browser, job_url)
                    if "error" in details.lower():
                        errors.append(f"Failed to get details for {job_url}")
                        continue
                        
                    # 6. LLM Score (Judgment step)
                    match_res = await score_job_match(
                        profile.model_dump(), 
                        job_url, 
                        details, 
                        threshold
                    )
                    
                    # 7. Threshold filter
                    job_tracker("save_job", job_id=job_url, company=job["company"], url=job_url, 
                               status="approved" if match_res.is_above_threshold else "rejected_llm", 
                               match_score=match_res.score)
                               
                    if not match_res.is_above_threshold:
                        continue
                        
                    # 8. Draft + Fill + Upload
                    cover_letter = await generate_cover_letter(profile.model_dump(), details)
                    
                    # We mock the form fields here since we don't have a real DOM parser yet
                    # A real system would use a tool to extract form schema, then map it.
                    form_fields = [
                        {"selector": "input[name='name']", "value": profile.name, "type": "text"},
                        {"selector": "input[name='email']", "value": profile.email, "type": "text"}
                    ]
                    
                    await fill_application(agent.browser, form_fields)
                    await upload_file(agent.browser, "input[type='file']", resume_path)
                    
                    job_tracker("update_status", job_id=job_url, status="staged")
                    
                    # 9. Submit (Gated)
                    if not dry_run:
                        submit_res = await submit_application(agent.browser, "button[type='submit']", confirm=True)
                        if "error" in submit_res.lower():
                            errors.append(f"Failed to submit {job_url}: {submit_res}")
                            job_tracker("update_status", job_id=job_url, status="failed_submit")
                        else:
                            jobs_applied += 1
                            job_tracker("update_status", job_id=job_url, status="submitted")
                    else:
                        # In dry run, we stop here and count it as "staged" (applied=1 for metrics)
                        jobs_applied += 1

    status = SkillStatus.SUCCESS if jobs_applied > 0 else (SkillStatus.PARTIAL if not errors else SkillStatus.FAILED)
    
    return SkillResult(
        status=status,
        summary=f"Processed {jobs_processed} jobs, staged/applied to {jobs_applied}. Dry run: {dry_run}",
        jobs_processed=jobs_processed,
        jobs_applied=jobs_applied,
        errors=errors
    )
