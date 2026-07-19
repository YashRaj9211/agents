# Web Automation

Small, model-driven browser automation built with Playwright MCP. The first
milestone is a reliable generic browser agent; job-search skills come next.

## What exists now

```
backend/main.py          command-line entry point
backend/agent/runner.py  model -> browser-tool -> observation loop
backend/browser_mcp/     Playwright MCP connection only
backend/llm/client.py    OpenAI-compatible model connection only
backend/memory.py        in-memory conversation plus JSONL trace
backend/tools/local.py   safe file, PDF-text, and HTML/CSS-to-PDF tools
backend/skills/          job-search and application-preparation skill prompts
```

There is deliberately no custom `click()`, `type()`, or `navigate()` wrapper.
Playwright MCP already provides those browser actions well.

## First-time setup

From `backend` in PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `LLM_API_KEY` and `LLM_MODEL`. Node.js 18+ is also required
because the agent launches `npx @playwright/mcp@latest`.

## Run

### Option A: Web UI Console (Recommended)

1. **Start the FastAPI Backend**:
   From `backend` in PowerShell:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python -m uvicorn api.app:app --host 127.0.0.1 --port 3000
   ```
2. **Start the Frontend Dev Server**:
   From `frontend` in a separate PowerShell window:
   ```powershell
   npm run dev -- --port 5173
   ```
3. Open your browser to **http://localhost:5173/** to configure runs and view real-time log streaming.

### Option B: Command Line

From `backend` in PowerShell:
```powershell
python main.py "Open example.com and tell me the page heading"
```

### Browser Profile Setup

The first run downloads Playwright MCP if needed. The browser profile is kept
in `backend/storage/browser-profile`. To manually log in (for sites like Google/LinkedIn) and bypass bot detection:
```powershell
npx playwright open --user-data-dir=storage/browser-profile
```
(Or run your local Google Chrome using that directory: `& "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="storage/browser-profile"`). Do not commit or share that folder.

## Deliberate safety boundary

The agent can browse and fill non-sensitive information, but it stops for
passwords, MFA, CAPTCHAs, payments, and irreversible submissions. We can add
an explicit approval flow before building job applications.

## First job-skill test

Copy a resume and a small profile into `backend/storage/files/input/`. The
search skill can inspect documents and create a shortlist, but will not apply:

```powershell
python main.py --skill job_search "Search LinkedIn for remote Python developer jobs in India and save the best 10 matches."
```

`job_apply` fills and prepares an application but stops before final submission:

```powershell
python main.py --skill job_apply "Open the saved job URL and prepare an application."
```

Put your resume at `backend/storage/files/input/resume.pdf`, then create
`backend/storage/files/input/profile.md` with target roles, location, skills,
experience, preferences, and safe reusable application answers.
