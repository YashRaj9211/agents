"""
Persistent store for the job-hunt pipeline (profile, scraped jobs, evaluations, tailored resumes).

Plain JSON files under ``data/jobhunt/`` (override with ``JOBHUNT_DIR``). Both the agent tools and
the HTTP API go through this module so they always see the same data. All writes are atomic and
guarded by a process-wide lock because parallel agent runs may write at the same time.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()

# Weights for the overall match score.
PARAMETER_WEIGHTS: Dict[str, int] = {
    "skills": 30,
    "experience": 20,
    "role_fit": 20,
    "location": 10,
    "compensation": 10,
    "growth": 5,
    "company": 5,
}

JOB_STATUSES = ("new", "shortlisted", "tailored", "applied", "rejected")


def _root() -> Path:
    env = os.getenv("JOBHUNT_DIR")
    base = Path(env) if env else Path(__file__).resolve().parents[3] / "data" / "jobhunt"
    (base / "resumes").mkdir(parents=True, exist_ok=True)
    return base


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read(name: str, default: Any) -> Any:
    path = _root() / name
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default


def _write(name: str, data: Any) -> None:
    path = _root() / name
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def job_id_for(url: str, title: str = "", company: str = "") -> str:
    """Stable id so re-scraping the same posting never creates a duplicate."""
    key = (url or "").split("#")[0].split("?")[0].strip().lower() or f"{title}|{company}".lower()
    return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]


# -- Profile ---------------------------------------------------------------

def get_profile() -> Dict[str, Any]:
    with _LOCK:
        return _read("profile.json", {})


def save_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    with _LOCK:
        current = get_profile()
        if current.get("sample") and not (profile or {}).get("sample"):
            current = {}  # a real profile replaces the sample one instead of merging into it
        merged = {**current, **(profile or {})}
        merged["updated_at"] = _now()
        _write("profile.json", merged)
        return merged


# -- Jobs ------------------------------------------------------------------

def _load_jobs() -> Dict[str, Dict[str, Any]]:
    return _read("jobs.json", {})


def list_jobs(status: Optional[str] = None, evaluated: Optional[bool] = None) -> List[Dict[str, Any]]:
    with _LOCK:
        jobs = list(_load_jobs().values())
    if status:
        jobs = [j for j in jobs if j.get("status") == status]
    if evaluated is not None:
        jobs = [j for j in jobs if bool(j.get("evaluation")) == evaluated]
    jobs.sort(
        key=lambda j: ((j.get("evaluation") or {}).get("overall", -1), j.get("scraped_at", "")),
        reverse=True,
    )
    return jobs


def get_job(job_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        return _load_jobs().get(job_id)


def add_jobs(jobs: List[Dict[str, Any]], source: str = "") -> Dict[str, Any]:
    """Insert scraped jobs, skipping ones without a title/company and merging duplicates."""
    added, merged, skipped = 0, 0, 0
    with _LOCK:
        store = _load_jobs()
        for raw in jobs or []:
            title = str(raw.get("title") or "").strip()
            company = str(raw.get("company") or "").strip()
            if not title or not company:
                skipped += 1
                continue
            jid = job_id_for(str(raw.get("url") or ""), title, company)
            skills = raw.get("skills") or []
            if isinstance(skills, str):
                skills = [s.strip() for s in skills.split(",") if s.strip()]
            record = {
                "title": title,
                "company": company,
                "location": str(raw.get("location") or "").strip(),
                "url": str(raw.get("url") or "").strip(),
                "source": str(raw.get("source") or source or "").strip(),
                "salary": str(raw.get("salary") or "").strip(),
                "posted": str(raw.get("posted") or "").strip(),
                "work_mode": str(raw.get("work_mode") or "").strip(),
                "experience_level": str(raw.get("experience_level") or "").strip(),
                "description": str(raw.get("description") or "").strip(),
                "skills": skills,
            }
            if jid in store:
                existing = store[jid]
                for k, v in record.items():
                    if v and not existing.get(k):
                        existing[k] = v
                merged += 1
            else:
                store[jid] = {"id": jid, **record, "status": "new", "scraped_at": _now(),
                              "evaluation": None, "resume": None}
                added += 1
        _write("jobs.json", store)
        total = len(store)
    return {"added": added, "duplicates_merged": merged, "skipped_invalid": skipped, "total_jobs": total}


def compute_overall(parameters: Dict[str, Dict[str, Any]]) -> int:
    total, weight = 0.0, 0
    for name, w in PARAMETER_WEIGHTS.items():
        entry = parameters.get(name)
        if not isinstance(entry, dict):
            continue
        try:
            score = max(0.0, min(100.0, float(entry.get("score"))))
        except (TypeError, ValueError):
            continue
        total += score * w
        weight += w
    return round(total / weight) if weight else 0


def verdict_for(overall: int) -> str:
    if overall >= 80:
        return "strong"
    if overall >= 65:
        return "good"
    if overall >= 50:
        return "stretch"
    return "skip"


def save_evaluations(evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Store matcher output. ``overall`` and ``verdict`` are computed here, never trusted from the LLM."""
    saved, unknown = 0, []
    with _LOCK:
        store = _load_jobs()
        for ev in evaluations or []:
            jid = str(ev.get("job_id") or "")
            if jid not in store:
                unknown.append(jid)
                continue
            params: Dict[str, Dict[str, Any]] = {}
            for name in PARAMETER_WEIGHTS:
                p = (ev.get("parameters") or {}).get(name)
                if isinstance(p, dict):
                    try:
                        score = max(0, min(100, int(round(float(p.get("score"))))))
                    except (TypeError, ValueError):
                        continue
                    params[name] = {"score": score, "note": str(p.get("note") or "")}
            overall = compute_overall(params)
            store[jid]["evaluation"] = {
                "overall": overall,
                "verdict": verdict_for(overall),
                "parameters": params,
                "why": [str(x) for x in ev.get("why") or []],
                "gaps": [str(x) for x in ev.get("gaps") or []],
                "red_flags": [str(x) for x in ev.get("red_flags") or []],
                "evaluated_at": _now(),
            }
            if store[jid]["status"] == "new" and overall >= 65:
                store[jid]["status"] = "shortlisted"
            saved += 1
        _write("jobs.json", store)
    return {"saved": saved, "unknown_job_ids": unknown}


def set_status(job_id: str, status: str) -> Optional[Dict[str, Any]]:
    if status not in JOB_STATUSES:
        raise ValueError(f"status must be one of {JOB_STATUSES}")
    with _LOCK:
        store = _load_jobs()
        if job_id not in store:
            return None
        store[job_id]["status"] = status
        _write("jobs.json", store)
        return store[job_id]


def delete_job(job_id: str) -> bool:
    with _LOCK:
        store = _load_jobs()
        if job_id not in store:
            return False
        del store[job_id]
        _write("jobs.json", store)
        f = resume_path(job_id)
        if f.exists():
            f.unlink()
        return True


def clear_jobs(sample_only: bool = False) -> int:
    with _LOCK:
        if sample_only and get_profile().get("sample"):
            (_root() / "profile.json").unlink(missing_ok=True)
        store = _load_jobs()
        keep = {k: v for k, v in store.items() if sample_only and v.get("source") != "sample"}
        for k in set(store) - set(keep):
            f = resume_path(k)
            if f.exists():
                f.unlink()
        _write("jobs.json", keep)
        return len(store) - len(keep)


# -- Tailored resumes ------------------------------------------------------

def resume_path(job_id: str) -> Path:
    return _root() / "resumes" / f"{job_id}.html"


def save_resume_html(job_id: str, html: str, template: str, notes: List[str]) -> Optional[Dict[str, Any]]:
    with _LOCK:
        store = _load_jobs()
        if job_id not in store:
            return None
        resume_path(job_id).write_text(html, encoding="utf-8")
        store[job_id]["resume"] = {"template": template, "generated_at": _now(), "notes": notes}
        if store[job_id]["status"] in ("new", "shortlisted"):
            store[job_id]["status"] = "tailored"
        _write("jobs.json", store)
        return store[job_id]


def read_resume_html(job_id: str) -> Optional[str]:
    f = resume_path(job_id)
    return f.read_text(encoding="utf-8") if f.exists() else None


def stats() -> Dict[str, Any]:
    jobs = list_jobs()
    evaluated = [j for j in jobs if j.get("evaluation")]
    by_status: Dict[str, int] = {s: 0 for s in JOB_STATUSES}
    for j in jobs:
        key = j.get("status", "new")
        by_status[key] = by_status.get(key, 0) + 1
    return {
        "total": len(jobs),
        "evaluated": len(evaluated),
        "strong": sum(1 for j in evaluated if j["evaluation"]["verdict"] == "strong"),
        "good": sum(1 for j in evaluated if j["evaluation"]["verdict"] == "good"),
        "tailored": sum(1 for j in jobs if j.get("resume")),
        "by_status": by_status,
        "has_profile": bool(get_profile()),
        "average_score": round(sum(j["evaluation"]["overall"] for j in evaluated) / len(evaluated)) if evaluated else 0,
    }
