# Naukri Job Application Skill

## Description
This skill automates the process of applying to jobs on Naukri.com using a saved browser profile with login credentials. It navigates to a specified Naukri job listing page (default homepage), processes job listings, clicks the "Apply" button for each job (Naukri Easy Apply), handles any additional questions (like relocation), and confirms submission. For jobs that require external application ("Apply on site"), it collects the link.

## Prerequisites
- A saved browser profile containing Naukri login credentials (e.g., `yash_job_profile`).
- The profile must be activated before running the skill.

## Steps

### 1. Activate Browser Profile
```text
set_browser_profile(profile_name="yash_job_profile")
```

### 2. Navigate to Naukri Job Listing Page
```text
browser_navigate(url="<starting_url>")
```
Wait for page load.
- For homepage: use `https://www.naukri.com` (expect URL to contain `/mnjuser/homepage`).
- For recommended jobs: use `https://www.naukri.com/mnjuser/recommendedjobs`.
- Collect the no of jobs available on the page.
- Start applying to each one by one
- Dont get stuck where it takes time
- For other job listing pages, adjust accordingly.

### 3. Locate Job Listings
- In the page snapshot, look for the job listing section (e.g., "Recommended jobs for you", "Job listings", etc.).
- Each job card is typically within a generic element with `cursor=pointer` and contains job title, company, location, etc.
- Example selector pattern: `div.filter({ hasText: /^Job Title$/ })` for clicking a specific job.

### 4. Process Each Job
For each visible job card in the listing:
1. Click the job title to open the job detail page in a new tab.
2. Switch to the new tab.
3. Wait for job detail page to load.
4. Locate the "Apply" button (typically a button with text "Apply" or role button with name "Apply").
5. Click the "Apply" button.
6. If an Apply Confirmation page appears (Naukri Easy Apply):
   - Check for any additional questions (e.g., relocation willingness).
   - If a radio button for "Yes"/"No" appears, select "Yes" if willing to relocate.
   - If a text box appears (e.g., "Type message here..."), optionally enter a brief message.
   - Click the "Save" or equivalent button to submit.
   - Wait for confirmation (look for success indicator or confirmation message).
   - Increment **Applied** count.
7. If instead of an Apply Confirmation page, you are redirected to an external site or see an "Apply on site" button/link:
   - Collect the URL (the current URL or the link href) as an "Apply on site" link.
   - Increment the **"Apply on Site" Links Collected** count.
   - Close the tab and return to the listing tab.
8. Close the job detail tab (if opened) and return to the job listing tab.

### 5. Track Applications
- Keep count of:
  - **Applied**: Number of successful Naukri Easy Apply submissions.
  - **Total Available**: Number of job cards processed in the listing section.
  - **Jobs Left to Apply**: Total Available - Applied (should be zero if all visible jobs are applied via Easy Apply).
  - **"Apply on Site" Links Collected**: Number of jobs that required external application (links collected).

## Notes
- The skill assumes jobs are presented in a scrollable list; if lazy loading is involved, scroll down to load more jobs before processing.
- Handle pop-ups or modals that may appear after clicking Apply (e.g., confirmation dialogs).
- If the Apply button is not visible or the job requires external application, note the "Apply on site" link for manual follow-up.
- Ensure the browser profile is up-to-date with Naukri login to avoid re-authentication prompts.
- After processing, return to the job listing tab for any further actions.
- The skill works on any Naukri job listing page with a similar structure (homepage, recommended jobs, search results, etc.).

## Example Workflow (from experience on recommended jobs page)
- Activated profile `yash_job_profile`.
- Navigated to https://www.naukri.com/mnjuser/recommendedjobs.
- Processed 7 recommended jobs:
  1. Backend Developer - Fan Tv Ai (Noida) -> Applied (Easy Apply)
  2. Lead Java FullStack Software Engineer - Epam Systems (Hyderabad/Pune/Chennai) -> Applied (Easy Apply)
  3. Software Engineer - Iospl Technology Services (Pune) -> Applied (Easy Apply)
  4. Fullstack Developer - Ventures Hrd Centre (Bengaluru) -> Applied (Easy Apply)
  5. Python Full stack Support Engineer - Tavant (Bengaluru) -> Applied (Easy Apply)
  6. Java Developer - CGI (Hyderabad) -> Applied (Easy Apply)
  7. Human Centered Analytics - Deloitte US-India Offices (Hyderabad/Pune/Bengaluru) -> Applied (Easy Apply) [answered relocation question: Yes]
- All applications were submitted via Naukri Easy Apply (no external "Apply on site" links encountered).
- Result: Applied = 7, Total Available = 7, Jobs Left to Apply = 0, "Apply on Site" Links Collected = 0.

## Output
Return a summary in markdown format:
```markdown
# Naukri Job Application Summary

## Actions Performed
- Activated browser profile `[profile_name]`
- Navigated to Naukri job listing page: `[starting_url]`
- Processed [X] job cards in the listing section

## Results
| Metric | Count |
|--------|-------|
| **Applied Jobs** | [A] |
| **Total Available Jobs** | [T] |
| **Jobs Left to Apply** | [L] |
| **"Apply on Site" Links Collected** | [C] |

## Applied Job List (Easy Apply)
1. [Job Title] - [Company] ([Location])
2. ...

## Apply on Site Links Collected (if any)
1. [Job Title] - [URL]
2. ...
```

## Error Handling
- If login is required, the skill should prompt to update the browser profile.
- If no apply button is found, skip the job and log as "no apply button".
- If application fails, capture error and continue with next job.