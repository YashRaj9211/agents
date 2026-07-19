# Job search

Find matching jobs and return a structured shortlist. Do not apply.

1. Read `input/profile.md` and, if present, `input/resume.pdf`.
2. Use only the candidate's stated roles, skills, location, and preferences.
3. Search the requested job board using its logged-in browser session. Collect title, company, location, job URL, and a concise match reason.
4. Save results to `output/job-shortlist.json`.
5. Stop for MFA, CAPTCHA, or an expired session.
