Last updated: 58396d3 2026-11-15
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Autopilot resumed on your words (2026-11-15): STATE `running`, `work limit from: 58396d3`, task re-enabled
(next tick 02:59 UTC). Merge the small PR that carries this STATE change into the working branch
(and `main`) BEFORE then, or the tick will still read `paused`. Then 2.3 slice 3 (Acceptance block
and the evaluation budget first); the first tick after a merge also writes the learning-log `DRAFT`.

## Open decisions
- **Scheduled task branch (your clicks):** `update_trigger` cannot change a task's repo or branch (it edits only name, schedule, enabled, model, prompt). Stored: repo `Mud0709/simforge`, push-outcome branch `claude/serene-feynman` (wrong), model Sonnet 5.5, disabled, one-line prompt. Set the branch to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming; the tick itself reads the working branch from HANDOFF on `origin/main`.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking: sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: pre-resume fixes (author's request, 2026-11-15)
- **Done locally and pushed (PR open, not merged):** SKILL.md step 1.2 and step 6: a `paused` autopilot ends with one line; only the author's words "resume autopilot" set `status: running`, never an `Answer:` line, a STATE edit or a comment. `blocked`/`waiting-review` keep the answer rule.
- **Verified:** SKILL.md on the working branch (`b7504bd`) is the new version: 8 agent files, the CLAUDE.md model-table pointer, the 4-subagent cap with the 5-Haiku-spawn limit (line 160). Stored task read back: Sonnet 5.5, disabled, prompt as shortened.
- **Not done:** the task's branch (no tool for it; see Open decisions). Autopilot stays paused.

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
