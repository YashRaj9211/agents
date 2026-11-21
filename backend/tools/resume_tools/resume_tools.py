import json
import os
from typing import Dict, Any, Union
from playwright.async_api import async_playwright

# 1. Embed the HTML and CSS template directly into the script
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Resume</title>
    <style>
        /* Base Print Styles for Yash-Raj-Resume_2.pdf Layout */
        @page { size: A4; margin: 0; }
        html, body { height: 297mm; overflow: hidden; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: white;
            color: #000;
        }

        #resume-container {
            width: 210mm;
            height: 297mm;
            overflow: hidden;
            padding: 10mm 12mm;
            box-sizing: border-box;
        }
        /* The fit script sets --z so the content fills ~97% of the single A4 page. */
        #fill { zoom: var(--z, 1); }

        /* Typography & Layout */
        h1 {
            text-align: center;
            text-transform: uppercase;
            font-size: 22px;
            margin: 0 0 5px 0;
            letter-spacing: 1px;
        }

        .contact-info {
            text-align: center;
            font-size: 12px;
            margin-bottom: 15px;
        }

        .section-title {
            font-size: 14px;
            text-transform: uppercase;
            border-bottom: 1px solid #000;
            margin-top: 15px;
            margin-bottom: 10px;
            font-weight: bold;
        }

        /* Skills Section */
        .skills-list {
            font-size: 12px;
            margin-bottom: 4px;
        }
        .skills-list strong {
            display: inline-block;
            width: 170px;
        }

        /* Generic Item Layout */
        .item-row {
            margin-bottom: 12px;
        }
        .item-header {
            display: flex;
            justify-content: space-between;
            font-weight: bold;
            font-size: 13px;
        }
        .item-subheader {
            display: flex;
            justify-content: space-between;
            font-style: italic;
            font-size: 12px;
            margin-top: 2px;
        }
        .item-bullets {
            margin-top: 5px;
            margin-bottom: 0;
            padding-left: 20px;
            font-size: 12px;
            line-height: 1.4;
        }

        /* Additional Section */
        .additional-list {
            font-size: 12px;
            margin-bottom: 4px;
        }
    </style>
</head>
<body>
    <div id="resume-container"><div id="fill">
        <h1 id="res-name"></h1>
        <div id="res-contact" class="contact-info"></div>

        <div class="section-title">Technical Skills</div>
        <div id="res-skills"></div>

        <div class="section-title">Work Experience</div>
        <div id="res-experience"></div>

        <div class="section-title">Projects</div>
        <div id="res-projects"></div>

        <div class="section-title">Education</div>
        <div id="res-education"></div>

        <div class="section-title">Additional</div>
        <div id="res-additional"></div>
    </div></div>

    <script>
        // Expose function globally so Playwright can invoke it
        window.buildResume = function(data) {
            data = data || {};
            document.getElementById('res-name').innerText = data.name || '';
            document.getElementById('res-contact').innerHTML = data.contact || '';

            document.getElementById('res-skills').innerHTML = (data.skills || []).map(skill => `
                <div class="skills-list"><strong>${skill.category || 'Skill'}:</strong> ${skill.items || ''}</div>
            `).join('');

            document.getElementById('res-experience').innerHTML = (data.experience || []).map(exp => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${exp.company || ''}</span>
                        <span>${exp.location || ''}</span>
                    </div>
                    <div class="item-subheader">
                        <span>${exp.title || ''}</span>
                        <span>${exp.dates || ''}</span>
                    </div>
                    <ul class="item-bullets">
                        ${(exp.bullets || []).map(bullet => `<li>${bullet}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

            document.getElementById('res-projects').innerHTML = (data.projects || []).map(proj => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${proj.title || ''}${proj.stack ? ' - ' + proj.stack : ''}</span>
                    </div>
                    <ul class="item-bullets">
                        ${(proj.bullets || []).map(bullet => `<li>${bullet}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

            document.getElementById('res-education').innerHTML = (data.education || []).map(edu => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${edu.institution || ''}</span>
                        <span>${edu.location || ''}</span>
                    </div>
                    <div class="item-subheader">
                        <span>${edu.degree || ''}${edu.cgpa ? ' &nbsp;&nbsp;&nbsp; ' + edu.cgpa : ''}</span>
                        <span>${edu.dates || ''}</span>
                    </div>
                </div>
            `).join('');

            document.getElementById('res-additional').innerHTML = (data.additional || []).map(add => `
                <div class="additional-list"><strong>${add.category || 'Additional'}:</strong> ${add.text || ''}</div>
            `).join('');
            window.fitPage();
        };

        window.fitPage = function() {
            var box = document.getElementById('resume-container');
            var fill = document.getElementById('fill');
            var cs = getComputedStyle(box);
            var avail = (box.clientHeight - parseFloat(cs.paddingTop) - parseFloat(cs.paddingBottom)) * 0.97;
            var lo = 0.7, hi = 1.6;
            for (var i = 0; i < 14; i++) {
                var mid = (lo + hi) / 2;
                fill.style.setProperty('--z', mid);
                if (fill.getBoundingClientRect().height <= avail) lo = mid; else hi = mid;
            }
            fill.style.setProperty('--z', lo);

            // Type size moves in coarse steps (a wrapped line can jump the height), so spend the
            // remaining space on even spacing between sections/items to land at ~97% fill.
            var gaps = [].slice.call(fill.querySelectorAll('.section-title, .item-row'));
            var left = avail - fill.getBoundingClientRect().height;
            if (gaps.length && left > 0) {
                var extra = Math.min(left / gaps.length / lo, 14);
                gaps.forEach(function(g) { g.style.paddingTop = extra + 'px'; });
            }
        };
    </script>
</body>
</html>
"""

def _normalize(d: Dict[str, Any]) -> Dict[str, Any]:
    """Accept the richer shapes agents produce (contact dict, list skills, education details)."""
    d = dict(d)
    c = d.get("contact")
    if isinstance(c, dict):
        parts = [str(c[k]) for k in ("email", "phone", "location") if c.get(k)]
        parts += [str(l.get("label") or l.get("url")) for l in (c.get("links") or []) if isinstance(l, dict)]
        d["contact"] = " | ".join(parts)
    d["skills"] = [
        {**g, "items": ", ".join(map(str, g["items"])) if isinstance(g.get("items"), list) else g.get("items", "")}
        for g in (d.get("skills") or []) if isinstance(g, dict)
    ]
    d["education"] = [
        {**e, "cgpa": e.get("cgpa") or e.get("details") or ""} for e in (d.get("education") or []) if isinstance(e, dict)
    ]
    return d


def _words(v: Any) -> int:
    if isinstance(v, str):
        return len(v.split())
    if isinstance(v, dict):
        return sum(_words(x) for x in v.values())
    if isinstance(v, list):
        return sum(_words(x) for x in v)
    return 0


def _density_problem(d: Dict[str, Any]) -> str:
    bullets = sum(len(x.get("bullets") or []) for k in ("experience", "projects")
                  for x in (d.get(k) or []) if isinstance(x, dict))
    words = _words({k: v for k, v in d.items() if k not in ("name", "contact")})
    if words < 330 or bullets < 10:
        return (f"Resume too thin for a full page ({words} words, {bullets} bullets; need >=330 words and >=10 "
                f"bullets). Read the full profile from the Obsidian vault and include every role, project, skill "
                f"group, certification and achievement.")
    if words > 650 or bullets > 20:
        return f"Resume too long for one page ({words} words, {bullets} bullets; max 650 / 20). Tighten it."
    return ""


async def generate_resume_pdf(resume_data: Union[Dict[str, Any], str], output_filename: str = "Generated-Resume.pdf") -> str:
    """
    Generates a professionally formatted PDF resume based on provided user data.
    This tool should be called when a user asks to generate, create, or export a resume to PDF.
    
    Args:
        resume_data (Union[Dict[str, Any], str]): A dictionary (or JSON string) containing the structured resume content. 
            Must include keys: 'name', 'contact', 'skills', 'experience', 'projects', 'education', and 'additional'.
            The output is exactly ONE A4 page auto-scaled to ~97% full, so supply enough content
            (>=330 words, >=10 bullets; max 650 words / 20 bullets) or the tool returns an error.
        output_filename (str, optional): The name of the output PDF file. Defaults to "Generated-Resume.pdf".
        
    Returns:
        str: A string confirming the absolute path where the PDF was saved, or an error message if it failed.
    """
    try:
        if isinstance(resume_data, str):
            try:
                resume_data = json.loads(resume_data)
            except Exception:
                pass

        if not isinstance(resume_data, dict):
            return "Error generating PDF: resume_data must be a dict or JSON object string."
        resume_data = _normalize(resume_data)
        problem = _density_problem(resume_data)
        if problem:
            return f"Error generating PDF: {problem}"

        async with async_playwright() as p:
            browser = await p.chromium.launch()
            page = await browser.new_page()

            # 2. Set the page content directly from the embedded HTML string
            await page.set_content(HTML_TEMPLATE)

            # 3. Inject the Python dictionary into the browser context 
            await page.evaluate("data => window.buildResume(data)", resume_data)

            # 4. Generate the PDF bytes directly in-memory (no local file on disk)
            pdf_bytes = await page.pdf(
                format="A4",
                prefer_css_page_size=True,
                print_background=True,
                margin={
                    "top": "0",
                    "right": "0",
                    "bottom": "0",
                    "left": "0"
                }
            )
            
            await browser.close()

            # 5. Store directly in Garage S3 object storage and record artifact in DB
            from app.services.storage_service import store_agent_artifact_async
            clean_filename = output_filename if output_filename.endswith(".pdf") else f"{output_filename}.pdf"
            artifact_record = await store_agent_artifact_async(
                name=clean_filename,
                content=pdf_bytes,
                kind="pdf",
                mime_type="application/pdf",
                origin="agent_generated",
                metadata={"generator": "job_assist_agent", "type": "resume_pdf"},
            )

            return (
                f"Success: Resume PDF successfully generated and stored in Garage Object Storage!\n"
                f"- Storage URI: {artifact_record['storage_uri']}\n"
                f"- Artifact ID: {artifact_record['id']}\n"
                f"- Download URL: {artifact_record['download_url']}\n"
                f"- File Size: {artifact_record['size_bytes']} bytes"
            )

            
    except Exception as e:
        return f"Error generating PDF: {str(e)}"
    
RESUME_TOOLS = [generate_resume_pdf]