# Git Conventions

How we name branches, write commits, merge, and raise pull requests.

## 1. Branches

`main` is the only long-lived branch. It is always deployable. Never commit to it directly.

### Format

```
<type>/<short-kebab-description>
```

Optionally include an issue number: `<type>/<issue>-<description>` (e.g. `fix/42-resume-parse-crash`).

### Types

| Type | Use for | Example |
|---|---|---|
| `feat` | New feature or capability | `feat/job-matcher-agent` |
| `fix` | Bug fix | `fix/chat-history-scroll` |
| `refactor` | Code change with no behavior change | `refactor/split-chat-service` |
| `docs` | Documentation only | `docs/git-conventions` |
| `chore` | Tooling, deps, config, CI | `chore/bump-adk-version` |
| `test` | Adding or fixing tests | `test/resume-tools` |
| `perf` | Performance improvement | `perf/job-store-queries` |
| `style` | Formatting or UI styling, no logic change | `style/sidebar-spacing` |
| `hotfix` | Urgent production fix, branched from `main` | `hotfix/auth-token-expiry` |
| `exp` | Throwaway experiment or spike (never merged as-is) | `exp/obscura-browser` |

### Rules

- Lowercase, hyphen-separated, 2-5 words, no spaces or underscores.
- One purpose per branch. Split unrelated work into separate branches.
- Branch from an up-to-date `main`.
- Keep branches short-lived (days, not weeks). Rebase or merge `main` in regularly.
- **Delete the branch after its PR is merged** (local and remote).

## 2. Commits

We follow [Conventional Commits](https://www.conventionalcommits.org/).

### Format

```
<type>(<optional scope>): <summary>

<optional body: what and why, wrapped at ~72 chars>

<optional footer: Closes #42, BREAKING CHANGE: ...>
```

### Rules

- Types are the same as branch types (`feat`, `fix`, `refactor`, `docs`, `chore`, `test`, `perf`, `style`).
- Summary: imperative mood ("add", not "added"), lowercase, no trailing period, max ~72 chars.
- Scope is the area touched: `backend`, `frontend`, `agents`, `tools`, `db`, `ci`, `docs`.
- Body explains **why**, not just what.
- One logical change per commit. Don't mix refactors with features.
- Don't commit secrets, `.env`, local DBs, or editor/tool config (`.claude/`, `.mcp.json`).

### Examples

```
feat(agents): add resume tailor agent
fix(frontend): prevent chat list from jumping on new message
refactor(backend): move job store queries into repository
chore(ci): cache pip dependencies
docs: add git conventions
feat(api)!: rename /chat to /sessions

BREAKING CHANGE: clients must update the endpoint path.
```

## 3. Pull Requests

### Title

Same format as a commit summary:

```
<type>(<scope>): <summary>
```

e.g. `feat(agents): add job matcher and resume tailor`

### Description template

```markdown
## Summary
- What changed and why (1-3 bullets)

## Changes
- Notable implementation details

## Testing
- How you verified it (commands, screenshots)

## Related
- Closes #<issue>
```

### Rules

- Target `main`.
- Keep PRs small and focused (aim for under ~400 changed lines).
- Mark as **Draft** until ready for review.
- CI must pass; resolve all review comments before merging.
- Self-review the diff before requesting review.
- Rebase or merge `main` into your branch and resolve conflicts **before** requesting review.

## 4. Merging

- Default: **Squash and merge**, so `main` keeps one clean commit per PR. The squash commit message must follow the commit format above (use the PR title, with `(#PR)` appended automatically).
- Use a regular merge commit only for long-running work where individual commits matter.
- Never force-push to `main`.
- Force-pushing your own feature branch is fine (use `--force-with-lease`).
- After merging: delete the branch, then `git checkout main && git pull`.

## 5. Quick workflow

```powershell
git checkout main
git pull
git checkout -b feat/short-description
# ...work, commit with conventional messages...
git push -u origin feat/short-description
gh pr create --base main --title "feat(scope): summary"
# after merge
git checkout main
git pull
git branch -d feat/short-description
```

## 6. Releases (optional)

Tag releases on `main` with semantic versions: `v<major>.<minor>.<patch>` (e.g. `v1.2.0`).
