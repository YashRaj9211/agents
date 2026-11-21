"""
Deterministic renderer: structured resume JSON -> ONE self-contained, exactly-one-page A4 HTML file (inline CSS,
one tiny inline fit-to-page script that scales type so the page is ~97% full, no external assets). The tailoring agent only supplies content; layout and styling live here so every
resume is consistent, print-ready (A4) and ATS-friendly.
"""
from __future__ import annotations

from html import escape
from typing import Any, Dict, List

TEMPLATES = ("modern", "classic")

_BASE_CSS = """
@page { size: A4; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body { font-family: 'Segoe UI', Calibri, Helvetica, Arial, sans-serif; color: #1c1c28; line-height: 1.42;
       background: #e9e7ee; -webkit-print-color-adjust: exact; print-color-adjust: exact; }
a { color: inherit; text-decoration: none; }
ul { margin: 4px 0 0; padding-left: 18px; }
li { margin: 0 0 2px; }
.page { width: 210mm; height: 297mm; overflow: hidden; margin: 14px auto; background: #fff; box-shadow: 0 6px 30px rgba(20,10,40,.15); }
.fill { zoom: var(--z, 1); }
@media print { body { background: #fff; } .page { margin: 0; box-shadow: none; } html, body { width: 210mm; height: 297mm; overflow: hidden; } }
.item { margin-bottom: 9px; break-inside: avoid; }
.row { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.muted { color: #5d5b6b; }
"""

_MODERN_CSS = """
:root { --accent: #5b3df5; --ink: #1c1c28; --soft: #f3f1fd; }
.page { display: grid; grid-template-columns: 68mm 1fr; }
aside { background: #1d1b34; color: #e8e6f7; padding: 14mm 8mm; }
aside h1 { font-size: 21px; line-height: 1.15; margin: 0 0 4px; color: #fff; letter-spacing: .2px; }
aside .headline { color: #b9b2ff; font-size: 12px; margin-bottom: 14px; }
aside h2 { font-size: 10.5px; text-transform: uppercase; letter-spacing: 1.6px; color: #b9b2ff; margin: 16px 0 6px;
           border-bottom: 1px solid rgba(255,255,255,.18); padding-bottom: 3px; }
aside .contact div { font-size: 11px; margin-bottom: 4px; word-break: break-word; }
aside .skill-group { margin-bottom: 8px; }
aside .skill-group b { display: block; font-size: 11px; color: #fff; margin-bottom: 3px; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { background: rgba(255,255,255,.1); border-radius: 10px; padding: 1px 8px; font-size: 10.5px; }
main { padding: 14mm 11mm 12mm 10mm; font-size: 11.5px; }
main h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 1.6px; color: var(--accent);
          margin: 0 0 8px; padding-bottom: 3px; border-bottom: 2px solid var(--soft); }
main section { margin-bottom: 15px; }
.summary { font-size: 12px; color: #34324a; }
.item .title { font-weight: 700; font-size: 12.5px; }
.item .where { color: var(--accent); font-weight: 600; }
.item .when { color: #5d5b6b; font-size: 11px; white-space: nowrap; }
.tech { color: #5d5b6b; font-size: 11px; }
"""

_CLASSIC_CSS = """
.page { padding: 13mm 14mm; font-size: 11.5px; font-family: Georgia, 'Times New Roman', serif; }
.page > .fill { width: 100%; }
header { text-align: center; margin-bottom: 8px; }
header h1 { margin: 0; font-size: 24px; letter-spacing: 2px; text-transform: uppercase; }
header .headline { font-size: 12.5px; margin-top: 2px; font-style: italic; }
header .contact { font-size: 11px; margin-top: 5px; }
header .contact span + span::before { content: '  |  '; color: #999; }
section { margin-bottom: 12px; }
h2 { font-size: 12px; text-transform: uppercase; letter-spacing: 1.4px; margin: 0 0 6px; border-bottom: 1px solid #111;
     padding-bottom: 2px; }
.item .title { font-weight: 700; }
.item .where { font-style: italic; }
.item .when { font-size: 11px; white-space: nowrap; }
.skill-line { margin-bottom: 3px; }
.tech { font-size: 11px; color: #444; }
"""

_FIT_JS = """<script>
(function(){
  var TARGET = 0.97;
  function fit(){
    var page = document.querySelector('.page'); if(!page) return;
    var fills = [].slice.call(page.querySelectorAll('.fill'));
    var cs = getComputedStyle(page), H = page.clientHeight;
    var zs = fills.map(function(f){
      var host = f.parentElement, hs = getComputedStyle(host);
      var avail = (host === page ? H - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)
                                 : H - parseFloat(hs.paddingTop) - parseFloat(hs.paddingBottom)) * TARGET;
      var lo = 0.7, hi = 1.7;
      for (var i = 0; i < 14; i++) {
        var mid = (lo + hi) / 2; f.style.setProperty('--z', mid);
        if (f.getBoundingClientRect().height <= avail) lo = mid; else hi = mid;
      }
      f.style.setProperty('--z', lo);
      return lo;
    });
    if (fills.length === 2) {  // modern: sidebar never bigger than the main column
      fills[0].style.setProperty('--z', Math.min(zs[0], zs[1]));
    }
  }
  window.addEventListener('load', fit);
  window.addEventListener('beforeprint', fit);
})();
</script>"""


def _e(value: Any) -> str:
    return escape(str(value or "").strip())


def _list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _bullets(items: Any) -> str:
    lis = "".join(f"<li>{_e(b)}</li>" for b in _list(items) if str(b or "").strip())
    return f"<ul>{lis}</ul>" if lis else ""


def _contact_parts(contact: Dict[str, Any]) -> List[str]:
    parts: List[str] = []
    for key in ("email", "phone", "location"):
        if contact.get(key):
            parts.append(_e(contact[key]))
    for link in _list(contact.get("links")):
        if isinstance(link, dict) and (link.get("url") or link.get("label")):
            label = _e(link.get("label") or link.get("url"))
            url = str(link.get("url") or "").strip()
            parts.append(f'<a href="{escape(url, quote=True)}">{label}</a>' if url else label)
    return parts


def _experience(resume: Dict[str, Any]) -> str:
    out = []
    for x in _list(resume.get("experience")):
        if not isinstance(x, dict):
            continue
        out.append(
            f'<div class="item"><div class="row"><span class="title">{_e(x.get("title"))}</span>'
            f'<span class="when">{_e(x.get("dates"))}</span></div>'
            f'<div class="row"><span class="where">{_e(x.get("company"))}</span>'
            f'<span class="when">{_e(x.get("location"))}</span></div>{_bullets(x.get("bullets"))}</div>'
        )
    return "".join(out)


def _projects(resume: Dict[str, Any]) -> str:
    out = []
    for p in _list(resume.get("projects")):
        if not isinstance(p, dict):
            continue
        stack = f'<span class="tech"> · {_e(p.get("stack"))}</span>' if p.get("stack") else ""
        link = ""
        if p.get("link"):
            link = f'<span class="when"><a href="{escape(str(p["link"]), quote=True)}">{_e(p["link"])}</a></span>'
        out.append(
            f'<div class="item"><div class="row"><span><span class="title">{_e(p.get("title"))}</span>{stack}</span>'
            f'{link}</div>{_bullets(p.get("bullets"))}</div>'
        )
    return "".join(out)


def _education(resume: Dict[str, Any]) -> str:
    out = []
    for ed in _list(resume.get("education")):
        if not isinstance(ed, dict):
            continue
        detail = f'<div class="muted">{_e(ed.get("details"))}</div>' if ed.get("details") else ""
        out.append(
            f'<div class="item"><div class="row"><span class="title">{_e(ed.get("institution"))}</span>'
            f'<span class="when">{_e(ed.get("dates"))}</span></div>'
            f'<div class="where">{_e(ed.get("degree"))}</div>{detail}</div>'
        )
    return "".join(out)


def _additional(resume: Dict[str, Any]) -> str:
    out = []
    for a in _list(resume.get("additional")):
        if isinstance(a, dict):
            cat = f"<b>{_e(a.get('category'))}:</b> " if a.get("category") else ""
            out.append(f'<div class="skill-line">{cat}{_e(a.get("text"))}</div>')
    return "".join(out)


def _section(title: str, body: str) -> str:
    return f"<section><h2>{title}</h2>{body}</section>" if body else ""


def _modern(resume: Dict[str, Any]) -> str:
    contact = resume.get("contact") or {}
    skills = ""
    for g in _list(resume.get("skills")):
        if isinstance(g, dict):
            items = g.get("items")
            items = items if isinstance(items, list) else [s.strip() for s in str(items or "").split(",") if s.strip()]
            chips = "".join(f'<span class="chip">{_e(i)}</span>' for i in items)
            skills += f'<div class="skill-group"><b>{_e(g.get("category"))}</b><div class="chips">{chips}</div></div>'
    contact_html = "".join(f"<div>{p}</div>" for p in _contact_parts(contact))
    summary = f'<p class="summary">{_e(resume.get("summary"))}</p>' if resume.get("summary") else ""
    side_extra = ""
    add = _additional(resume)
    if add:
        side_extra = f"<h2>Additional</h2><div style='font-size:11px'>{add}</div>"
    return (
        f'<div class="page"><aside><div class="fill"><h1>{_e(resume.get("name"))}</h1>'
        f'<div class="headline">{_e(resume.get("headline"))}</div>'
        f'<h2>Contact</h2><div class="contact">{contact_html}</div>'
        f'<h2>Skills</h2>{skills}{side_extra}</div></aside>'
        f'<main><div class="fill">{_section("Profile", summary)}{_section("Experience", _experience(resume))}'
        f'{_section("Projects", _projects(resume))}{_section("Education", _education(resume))}</div></main></div>'
    )


def _classic(resume: Dict[str, Any]) -> str:
    contact = resume.get("contact") or {}
    contact_html = "".join(f"<span>{p}</span>" for p in _contact_parts(contact))
    skills = ""
    for g in _list(resume.get("skills")):
        if isinstance(g, dict):
            items = g.get("items")
            items = ", ".join(map(str, items)) if isinstance(items, list) else str(items or "")
            skills += f'<div class="skill-line"><b>{_e(g.get("category"))}:</b> {_e(items)}</div>'
    summary = f"<p>{_e(resume.get('summary'))}</p>" if resume.get("summary") else ""
    return (
        f'<div class="page"><div class="fill"><header><h1>{_e(resume.get("name"))}</h1>'
        f'<div class="headline">{_e(resume.get("headline"))}</div><div class="contact">{contact_html}</div></header>'
        f'{_section("Summary", summary)}{_section("Technical Skills", skills)}'
        f'{_section("Experience", _experience(resume))}{_section("Projects", _projects(resume))}'
        f'{_section("Education", _education(resume))}{_section("Additional", _additional(resume))}</div></div>'
    )


def render_resume_html(resume: Dict[str, Any], template: str = "modern", target: str = "") -> str:
    """Render ``resume`` into a complete HTML document string."""
    template = template if template in TEMPLATES else "modern"
    css = _BASE_CSS + (_MODERN_CSS if template == "modern" else _CLASSIC_CSS)
    body = _modern(resume) if template == "modern" else _classic(resume)
    title = f'{_e(resume.get("name")) or "Resume"}' + (f" - {_e(target)}" if target else "")
    return (
        '<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{title}</title><style>{css}</style></head><body>{body}{_FIT_JS}</body></html>"
    )
