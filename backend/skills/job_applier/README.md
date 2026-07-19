# Adding New Skills

The `job_applier` is just one skill consuming from the shared `tools/` library. 
You can easily create new skills by reusing the same tools.

## Example: Outreach Skill
If you wanted to build a skill that sends networking messages instead of applying to jobs:

1. Create `skills/outreach/skill.py` extending `Skill`.
2. Define its required tools: `["resume", "generation", "web"]`.
3. In `workflow.py`, you can reuse:
   - `analyze_resume` to understand the candidate's profile.
   - `search_jobs` to find target companies (and perhaps a new `search_people` tool).
   - `generate_cover_letter` (repurposed via a different prompt into `generate_networking_message`).
   - Browser MCP tools to send the message.

## Rules
- **Tools do not import from skills.** Tools live in `tools/` and are agnostic of the skill using them.
- **Skills orchestrate.** They string together deterministic tool calls and hand off to the LLM agent loop only for steps requiring judgment (e.g., scoring a match, handling an unexpected popup).
