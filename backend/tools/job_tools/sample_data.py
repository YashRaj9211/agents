"""Clearly-labelled SAMPLE data (source='sample') used only to preview the Job Hunt dashboard."""
from __future__ import annotations

from typing import Any, Dict

from tools.job_tools import job_store
from tools.job_tools.resume_renderer import render_resume_html

_SAMPLE_PROFILE = {
    "name": "Sample Candidate",
    "headline": "Backend Engineer",
    "contact": {"email": "sample@example.com", "location": "Remote", "links": [{"label": "github.com/sample", "url": "https://github.com/sample"}]},
    "summary": "Sample profile used to preview the dashboard.",
    "target_roles": ["Backend Engineer", "AI Engineer"],
    "locations": ["Remote", "Bengaluru"],
    "years_experience": 3,
    "skills": [{"category": "Backend", "items": ["Python", "FastAPI", "PostgreSQL"]}],
    "experience": [{"company": "Sample Co", "title": "Software Engineer", "location": "Remote", "dates": "2023 - Present",
                    "bullets": ["Built REST APIs serving 1M requests per day.", "Cut p95 latency by 40% with caching."]}],
    "projects": [{"title": "Agent Orchestrator", "stack": "Python, Google ADK", "bullets": ["Multi-agent job pipeline."]}],
    "education": [{"institution": "Sample University", "degree": "B.Tech, Computer Science", "dates": "2019 - 2023"}],
    "additional": [],
}

_ROWS = [
    ("Backend Engineer, AI Platform", "Orbit Labs", "Remote (India)", "Remote", "INR 28-40 LPA", "LinkedIn", ["Python", "FastAPI", "Postgres", "LLMs"],
     {"skills": 92, "experience": 85, "role_fit": 94, "location": 100, "compensation": 80, "growth": 88, "company": 75},
     ["FastAPI + Postgres is exactly the candidate's core stack", "Agent orchestration project maps to the platform work"], ["No Kafka experience"], []),
    ("AI Engineer (Agents)", "Nimbus AI", "Bengaluru", "Hybrid", "INR 30-45 LPA", "Wellfound", ["Python", "LLM", "Tool use", "Docker"],
     {"skills": 88, "experience": 72, "role_fit": 90, "location": 80, "compensation": 85, "growth": 92, "company": 70},
     ["Builds multi-agent systems like the candidate's Google ADK project"], ["Asks 4+ yrs; candidate has 3"], []),
    ("Software Engineer II", "Fintrack", "Pune", "Onsite", "INR 22-30 LPA", "Naukri", ["Java", "Spring", "SQL"],
     {"skills": 48, "experience": 70, "role_fit": 60, "location": 45, "compensation": 62, "growth": 55, "company": 68},
     ["Solid fintech brand"], ["Java/Spring required, candidate is Python-first", "Onsite in Pune"], ["Stack mismatch"]),
    ("Python Developer", "ByteForge", "Remote", "Remote", "", "Naukri", ["Python", "Django", "AWS"],
     {"skills": 74, "experience": 80, "role_fit": 72, "location": 100, "compensation": 50, "growth": 60, "company": 55},
     ["Python-first role, fully remote"], ["Salary not listed", "Django rather than FastAPI"], []),
    ("Senior ML Platform Engineer", "Quanta", "Hyderabad", "Hybrid", "INR 45-60 LPA", "LinkedIn", ["Python", "Kubernetes", "MLOps", "Spark"],
     {"skills": 55, "experience": 35, "role_fit": 68, "location": 60, "compensation": 90, "growth": 85, "company": 82},
     ["Strong comp and growth"], ["Needs 7+ yrs", "No Kubernetes/Spark depth"], ["Seniority far above candidate"]),
    ("Full Stack Developer", "Pixelbarn", "Remote", "Remote", "INR 15-22 LPA", "Indeed", ["React", "Node", "TypeScript"],
     {"skills": 52, "experience": 75, "role_fit": 50, "location": 100, "compensation": 40, "growth": 50, "company": 45},
     ["Remote friendly"], ["Frontend-heavy", "Below target pay"], ["Vague job description"]),
]


def load_sample_jobs() -> Dict[str, Any]:
    if not job_store.get_profile():
        job_store.save_profile({**_SAMPLE_PROFILE, "sample": True})
    jobs, evaluations = [], []
    for title, company, loc, mode, salary, src, skills, scores, why, gaps, flags in _ROWS:
        url = f"https://example.com/sample/{company.lower().replace(' ', '-')}"
        jobs.append({"title": title, "company": company, "location": loc, "work_mode": mode, "salary": salary,
                     "url": url, "source": "sample", "skills": skills, "posted": "2 days ago",
                     "description": f"SAMPLE posting for {title} at {company}. Skills: {', '.join(skills)}."})
        evaluations.append({
            "job_id": job_store.job_id_for(url, title, company),
            "parameters": {k: {"score": v, "note": f"Sample note for {k}"} for k, v in scores.items()},
            "why": why, "gaps": gaps, "red_flags": flags,
        })
    result = job_store.add_jobs(jobs, source="sample")
    job_store.save_evaluations(evaluations)
    top = evaluations[0]["job_id"]
    html = render_resume_html(_SAMPLE_PROFILE, "modern", "Backend Engineer, AI Platform @ Orbit Labs")
    job_store.save_resume_html(top, html, "modern", ["Sample resume: moved FastAPI project first to mirror the posting"])
    return result
