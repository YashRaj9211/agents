import os
from typing import Dict, Any
from playwright.sync_api import sync_playwright

# 1. Embed the HTML and CSS template directly into the script
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Resume</title>
    <style>
        /* Base Print Styles for Yash-Raj-Resume_2.pdf Layout */
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: white;
            color: #000;
        }

        #resume-container {
            width: 100%;
            padding: 10mm 12mm;
            box-sizing: border-box;
        }

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
    <div id="resume-container">
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
    </div>

    <script>
        // Expose function globally so Playwright can invoke it
        window.buildResume = function(data) {
            document.getElementById('res-name').innerText = data.name;
            document.getElementById('res-contact').innerHTML = data.contact;

            document.getElementById('res-skills').innerHTML = data.skills.map(skill => `
                <div class="skills-list"><strong>${skill.category}:</strong> ${skill.items}</div>
            `).join('');

            document.getElementById('res-experience').innerHTML = data.experience.map(exp => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${exp.company}</span>
                        <span>${exp.location}</span>
                    </div>
                    <div class="item-subheader">
                        <span>${exp.title}</span>
                        <span>${exp.dates}</span>
                    </div>
                    <ul class="item-bullets">
                        ${exp.bullets.map(bullet => `<li>${bullet}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

            document.getElementById('res-projects').innerHTML = data.projects.map(proj => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${proj.title} - ${proj.stack}</span>
                    </div>
                    <ul class="item-bullets">
                        ${proj.bullets.map(bullet => `<li>${bullet}</li>`).join('')}
                    </ul>
                </div>
            `).join('');

            document.getElementById('res-education').innerHTML = data.education.map(edu => `
                <div class="item-row">
                    <div class="item-header">
                        <span>${edu.institution}</span>
                        <span>${edu.location}</span>
                    </div>
                    <div class="item-subheader">
                        <span>${edu.degree} &nbsp;&nbsp;&nbsp; ${edu.cgpa}</span>
                        <span>${edu.dates}</span>
                    </div>
                </div>
            `).join('');

            document.getElementById('res-additional').innerHTML = data.additional.map(add => `
                <div class="additional-list"><strong>${add.category}:</strong> ${add.text}</div>
            `).join('');
        };
    </script>
</body>
</html>
"""

def generate_resume_pdf(resume_data: Dict[str, Any], output_filename: str = "Generated-Resume.pdf") -> str:
    """
    Generates a professionally formatted PDF resume based on provided user data.
    This tool should be called when a user asks to generate, create, or export a resume to PDF.
    
    Args:
        resume_data (Dict[str, Any]): A dictionary containing the structured resume content. 
            Must include keys: 'name', 'contact', 'skills', 'experience', 'projects', 'education', and 'additional'.
        output_filename (str, optional): The name of the output PDF file. Defaults to "Generated-Resume.pdf".
        
    Returns:
        str: A string confirming the absolute path where the PDF was saved, or an error message if it failed.
    """
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()

            # 2. Set the page content directly from the embedded HTML string
            page.set_content(HTML_TEMPLATE)

            # 3. Inject the Python dictionary into the browser context 
            page.evaluate("data => window.buildResume(data)", resume_data)

            # 4. Generate and save the PDF
            page.pdf(
                path=output_filename,
                format="A4",
                print_background=True,
                margin={
                    "top": "0",
                    "right": "0",
                    "bottom": "0",
                    "left": "0"
                }
            )
            
            browser.close()
            
            return f"Success: Resume PDF successfully generated and saved at {os.path.abspath(output_filename)}"
            
    except Exception as e:
        return f"Error generating PDF: {str(e)}"
    
RESUME_TOOLS = [generate_resume_pdf]