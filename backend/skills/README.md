# Skills (next step)

The browser agent is working directly from a user goal first. A skill will later
be a short specification, not a separate browser wrapper.

Example future skill: `job_search.md`

- Goal: find jobs matching the candidate profile.
- Inputs: title, location, filters.
- Success: return structured job details; do not apply.
- Constraints: use the logged-in browser profile and stop for CAPTCHA/MFA.

The same `BrowserAgent` runner will execute skills. We will add job-search
skills only after the generic agent is tested.
