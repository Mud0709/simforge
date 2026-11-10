---
name: simforge-status
description: Reorient on SimForge from the actual repository state and report status. Use when the user returns after a break or asks "where are we", after a milestone is merged, at the end of a meaningful task (to write the handoff), or when asked for a status report or a learning-log entry.
---

# SimForge status and handoffs

Git and the repository are the source of truth, not conversation history or summaries. Start
from the cheapest source that answers the question, label anything you did not verify, and
keep it short. Never re-read the whole conversation or whole documents to reorient.

## 1. Gather facts (read-only; stop as soon as the question is answered)

1. **The session brief** printed by the start hook (`.claude/hooks/session-start.sh`): branch,
   HEAD, latest merge on `main`, unmerged work, the 🔜 step and the handoff's next action and
   open decisions. If it is not in context, run the hook script; it needs no network. On a
   branch other than the working branch (named on `origin/main`) it warns and shows the
   working branch's handoff from `origin/<working branch>`: switch before doing any work.
2. **`docs/HANDOFF.md`**, read in full (it is short). If the brief warns that it is stale,
   rebuild the facts from `git log` since its `Last updated` sha; if it is missing, from
   `git log` since the latest merge on `main`.
3. Only if needed: `git fetch origin` (the brief uses the last fetched `origin/main`); open
   PRs and the check runs on their head commit (GitHub tools), noted as passed, failed,
   pending or not run; the `ROADMAP.md` row for the 🔜 step (search for it, do not read the
   file); `git log --oneline -5 -- docs/` for what changed in the docs (rely on git, never on
   the guides' own changelog sections, and never guess).
- Do not run the check suite unless asked; say which checks were and were not run.

## 2. Choose the output

**Session Start Brief (start of a session, or "where are we"):** at most about 10 lines:
branch and HEAD; latest merged milestone; unmerged work (commits, PR, uncommitted files);
the relevant roadmap step; open decisions; the single most useful next action.

**Task Completion Handoff (end of a meaningful task):** reply in `CLAUDE.md`'s format, then
**overwrite** `docs/HANDOFF.md` from the template already in that file (keep its headings, so
the hook can read them; about 60 lines at most). Rules for it:
- `Last updated: <sha> <YYYY-MM-DD>`, where the sha is the latest commit the handoff describes,
  then `Working branch: <branch>` (the fresh-session autopilot reads it from `main`, so a change
  of branch reaches it only once merged). Writing the handoff is the last step of a task, so the
  handoff's own commit comes after that sha; the hook warns once HEAD is more than 3 commits
  past it.
- States stay distinct: done locally, committed, pushed, PR open, merged. Name the commit
  or PR for each claim.
- Checks: exact commands that ran and their results; say what did not run.
- "Open decisions" is the only list of what the author must decide. Remove answered items.
  STATE and the journal link to it rather than copying it.
- The learning handoff: what the feature does in plain English, why it matters, the key
  concept, one design trade-off, and what the author should be able to explain themself.

**Milestone status report (on request):** the same fields as the handoff, for the whole
milestone, linking to `docs/HANDOFF.md`, the PR and the docs instead of restating them.

**Learning-log entry (after a merge):** draft it from the handoff's learning section in the
format of `docs/LEARNING_LOG.md` (newest first): milestone and merged commit, what it does,
key concepts, decisions and trade-offs, what to revisit, next. Write it at the top of the log
with its heading ending ` (DRAFT, awaiting the author)`, in the branch of the next change,
and list it under "Open decisions". The author approves by removing the tag (or says so in
chat); never remove it yourself without that. The autopilot's first tick after a merge does
this as its unit (autopilot skill, step 2.4b), so check for an existing draft first.

## 3. Rules

- Mark each claim as verified (name the command or source) or as an assumption.
- Never call work complete because code exists: complete means checks ran and passed, and
  for merged work, the merge commit is on `main`.
- Do not duplicate existing documentation; link to it.
- End with the recommended skill for the next step, in one line (`CLAUDE.md`).
