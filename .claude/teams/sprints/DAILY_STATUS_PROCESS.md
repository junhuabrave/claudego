# Daily Status Update Process

**Effective:** 2026-03-17
**Owner:** Engineering Director
**Applies to:** All 5 teams

---

## Purpose

Every team files a short status update **before starting work each day**. This catches blockers
early, keeps the director informed without meetings, and creates a paper trail for cross-team
coordination.

---

## Process

### When
- **Daily, before any code work begins**
- If a team has no updates (e.g., weekend, holiday), skip that day — no empty files

### Where
- Directory: `.claude/teams/sprints/daily/`
- Filename: `YYYY-MM-DD-<team>.md` (e.g., `2026-03-17-backend.md`)
- One file per team per day

### Who Files
- The team lead or whoever opens the session that day
- If using Claude Code, the agent should check for and create the daily update at session start

### How to Start a Session
1. Pull latest from `main`
2. Check `.claude/teams/sprints/daily/` for today's files from other teams — read them for cross-team context
3. Create your team's daily update using the template below
4. Commit and push before starting feature work

---

## Template

```markdown
# Daily Status — [Team Name]

**Date:** YYYY-MM-DD
**Branch:** `claude/<branch-name>`
**Phase 1 Sprint Day:** X of 14

## Yesterday
- [What shipped / what was worked on — be specific with file names and PR numbers]

## Today
- [What the team will work on today — reference sprint task numbers]

## Blockers
- [Any blockers or dependencies on other teams — or "None"]

## Notes
- [Optional: decisions made, risks discovered, scope changes]
```

---

## Team Branch Registry

Each team works on a dedicated long-lived branch. **Always reference this table when opening
a new session** so you know which branch to check out.

| Team | Branch | Worktree Path | Status |
|------|--------|---------------|--------|
| **Backend Python** | `claude/backend-sprint-p0` | — | Active — DB pool tuning, Redis cache |
| **Frontend React** | `claude/compassionate-rhodes` | — | Active — Vite migration, lazy loading, pagination |
| **Auth & Security** | `claude/romantic-goldstine` | `~/.claude/worktrees/romantic-goldstine` | Active — security headers, JWT guard |
| **Test Engineering** | `claude/continue-development-q8xZU` | — | Active — merged to main, rebased |
| **DevOps / CI-CD** | `claude/youthful-mendel` | — | Merged (PRs #16, #17) — Docker PYTHONPATH, Secrets Manager |
| **Engineering Director** | `claude/reverent-dijkstra` | `~/.claude/worktrees/reverent-dijkstra` | Active — standards, sprint briefs, hiring roadmap |

> **Note:** When a team's branch is merged and a new sprint starts, update this table with the
> new branch name. Keep historical branches as comments or delete the row.

---

## Review Flow

```
Team files daily update (before work)
         │
         ▼
Director reviews all 5 updates (async)
         │
         ├── No blockers → Teams proceed
         │
         └── Blocker found → Director coordinates
              │
              ├── Cross-team dependency → Tag both teams, set priority
              └── External blocker → Escalate to CTO / unblock
```

---

## Retention

- Keep daily files for the duration of the sprint (2 weeks)
- At sprint end, summarize key events in the sprint retrospective
- Archive or delete daily files older than 1 sprint

---

## Example

See: `daily/2026-03-17-backend.md` (template example below)

```markdown
# Daily Status — Backend Python

**Date:** 2026-03-17
**Branch:** `claude/backend-sprint-p0`
**Phase 1 Sprint Day:** 1 of 14

## Yesterday
- No prior sprint work — sprint kickoff today

## Today
- Task 1: Begin Redis cache integration (install redis + fakeredis, create `app/core/cache.py`)
- Task 2: DB connection pool tuning (`pool_size=20, max_overflow=10` in `database.py`)

## Blockers
- Redis not yet in `docker-compose.yml` — DevOps to add (Task 2 in devops-sprint)
- Using fakeredis locally until staging Redis is provisioned

## Notes
- Confirmed `get_redis()` singleton pattern with well-known cache keys (not per-user)
```
