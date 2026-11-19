Last updated: 9748111 2026-11-19
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Review and merge the draft PR `claude/determined-meitner-xpu871` into the working branch: the
autopilot's unit becomes a whole roadmap step (plan tick, then build tick). Then the next tick
builds 2.3 slice 5 (docs, full `check.sh --e2e`, whole-step review), writes the 2.3 step brief in
`docs/briefs/` and opens the 2.3 PR (it never merges). Read the learning-log draft (top of
`docs/LEARNING_LOG.md`) and approve it when you can.

## Open decisions
- **Learning-log draft for PR #20 and #23:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Scheduled task branch (your clicks):** `update_trigger` cannot change a task's repo or branch (it edits only name, schedule, enabled, model, prompt). Stored: repo `Mud0709/simforge`, push-outcome branch `claude/serene-feynman` (wrong), model Sonnet 5.5, disabled, one-line prompt. Set the branch to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming; the tick itself reads the working branch from HANDOFF on `origin/main`.
- **Next.js 16.4.1 security notice:** the first `npm run build` stops with SecurityFatalError, a retry passes; decide on upgrading. Not blocking.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers for every model (add `strict=True`?). Sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: a whole step per tick (author's request, 2026-11-19)
- **Done locally, committed, pushed (draft PR, not merged):** SKILL.md: unit = a roadmap step; plan tick, then build tick (every slice: test writer, builder, fresh reviewer if risky, one commit each; then full check, learning-guide chapter, step brief, whole-step review, the PR); caps 4 working subagents per slice and 24 per tick, 5 Haiku helpers per slice, work limit 12 commits; a finished step waits for your merge (one line per tick). New commit trailer `Autopilot-run: slice` (daily cap still counts `work`, one per tick). `docs/briefs/_template.md`: one-page step brief (IB terms, claims labelled proved, tested or observed, a two-minute demo, three questions) for your portfolio.
- **Also fixed (it would have blocked every build tick):** the guard-rail hook treated `python3 scripts/doc_index.py > /dev/null` as a write to `scripts/`; it now blocks only real writes to a guard-rail path (redirect target, `tee`, `cp`, `sed -i`, `git checkout`...), and heredoc text is data. Docs index regenerated; two guide excerpt line references updated.
- **Verified:** `backend/tests/scripts` passes (hook tests for `slice`, the script run, heredoc and every write form); full backend run: see the PR. **Not verified:** how long a scheduled session can run, so a long build tick may end early; its commits are safe and the next tick resumes at the next slice.
- **Not enforceable by script:** the per-slice and per-tick subagent caps, the 12-commit work limit, "slice N+1 only after slice N".

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
