import pytest

from tools.job_tools import job_store
from tools.job_tools.job_tools import (
    build_tailored_resume,
    list_jobs_to_evaluate,
    save_job_evaluations,
    save_scraped_jobs,
)
from tools.job_tools.resume_renderer import render_resume_html


@pytest.fixture(autouse=True)
def tmp_store(tmp_path, monkeypatch):
    monkeypatch.setenv("JOBHUNT_DIR", str(tmp_path))


def _job(n=1, **kw):
    return {"title": f"Backend Engineer {n}", "company": f"Co{n}", "url": f"https://x.com/j/{n}?utm=1", **kw}


def test_dedupe_and_validation():
    r = save_scraped_jobs([_job(1), _job(1), {"title": "", "company": "x"}], source="Test")
    assert r["added"] == 1 and r["duplicates_merged"] == 1 and r["skipped_invalid"] == 1
    assert r["total_jobs"] == 1


def test_evaluation_overall_computed_and_shortlist():
    save_scraped_jobs([_job(1), _job(2)])
    jobs = list_jobs_to_evaluate(10)["jobs"]
    assert len(jobs) == 2
    good = {k: {"score": 90, "note": "n"} for k in job_store.PARAMETER_WEIGHTS}
    bad = {k: {"score": 20, "note": "n"} for k in job_store.PARAMETER_WEIGHTS}
    out = save_job_evaluations([
        {"job_id": jobs[0]["id"], "parameters": good, "overall": 1, "why": ["a"]},
        {"job_id": jobs[1]["id"], "parameters": bad},
        {"job_id": "nope", "parameters": good},
    ])
    assert out["saved"] == 2 and out["unknown_job_ids"] == ["nope"]
    ranked = job_store.list_jobs()
    assert ranked[0]["evaluation"]["overall"] == 90 and ranked[0]["evaluation"]["verdict"] == "strong"
    assert ranked[0]["status"] == "shortlisted"
    assert ranked[1]["evaluation"]["verdict"] == "skip" and ranked[1]["status"] == "new"
    assert list_jobs_to_evaluate()["remaining"] == 0


def test_resume_is_single_file_and_escaped():
    save_scraped_jobs([_job(1)])
    jid = job_store.list_jobs()[0]["id"]
    resume = {"name": "A <b>Dev</b>", "headline": "Eng", "contact": {"email": "a@b.c"},
              "skills": [{"category": "Lang", "items": ["Python", "Go"]}],
              "experience": [{"company": "X", "title": "Dev", "dates": "2020", "bullets": ["did <script>alert(1)</script>"]}]}
    for tpl in ("modern", "classic"):
        res = build_tailored_resume(jid, resume, template=tpl, change_notes=["n"])
        assert res["ok"]
        html = job_store.read_resume_html(jid)
        assert "<script>" not in html and "&lt;script&gt;" in html
        assert html.count("<style>") == 1 and "http://" not in html.split("</style>")[0]
    assert job_store.get_job(jid)["status"] == "tailored"
    assert not build_tailored_resume("missing", resume)["ok"]


def test_render_handles_empty_resume():
    assert "<html" in render_resume_html({"name": "Only Name"})
