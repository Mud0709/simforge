---
name: simforge-status
description: Reorient on SimForge from the actual repository state and report status. Use when the user returns after a break or asks "where are we", after a milestone is merged, or when asked for a status report or a learning-log entry.
---

# SimForge status

The repository and GitHub are the source of truth, not earlier conversation summaries.
Report what you verified, label anything you did not verify, and keep it short.

## 1. Gather facts (read-only; change nothing)

- `git fetch origin` then `git log --oneline -10 origin/main` and `git status -sb`.
- Open pull requests for the repository and, for each, the check runs on its head commit
  (GitHub tools). Note CI as passed, failed, pending or not run.
- `ROADMAP.md`: the step marked 🔜, the last ✅ steps, and the Track A table (optional,
  never a prerequisite).
- The newest entries in the learning guides' changelogs (`docs/*LEARNING_GUIDE.md`).
- Do not run the full check suite unless asked; say which checks were and were not run.

## 2. Choose the output

**Reorientation (after a break):** where SimForge stands (last merged milestone and commit),
what is in progress (branches, open PRs, uncommitted work), what the next roadmap step is
meant to achieve, and the one or two concepts to understand before starting it.

**Milestone status report:**
- Completed work and its purpose.
- Important files, components or interfaces affected.
- Key design decisions and their rationale.
- Tests and checks actually run, including failures.
- State: uncommitted, committed, in a PR, merged, or awaiting verification.
- Remaining limitations and unresolved questions.
- Next recommended milestone and why it should come next.

**Learning-log entry (after a merge), compact enough to save:**
- Milestone and merged commit.
- What the feature does.
- Key concepts learned.
- Important decisions and trade-offs.
- Questions to revisit.
- Next step.

## 3. Rules

- Mark each claim as verified (name the command or source) or as an assumption.
- Never call work complete because code exists: complete means checks ran and passed, and
  for merged work, the merge commit is on `main`.
- Do not duplicate existing documentation; link to it.
- Finish with "What this means for me" and the recommended skill for the next step
  (see the Skills section of `CLAUDE.md`).
