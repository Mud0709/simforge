Last updated: learning-log draft tick 2026-11-19
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
2.3 is merged (PR #26). The next tick moves 🔜 to 2.4, adds the 2.3 step-cost line and writes the 2.4 plan. Approve the learning-log drafts when you can; try the oscillator demo in `docs/briefs/2.3.md` (not run in a browser yet).

## Open decisions
- **Learning-log drafts for PR #20, #23 and #26:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Scheduled task branch (your clicks):** `update_trigger` cannot change a task's repo or branch (it edits only name, schedule, enabled, model, prompt). Stored: repo `Mud0709/simforge`, push-outcome branch `claude/serene-feynman` (wrong), model Sonnet 5.5, disabled, one-line prompt. Set the branch to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming; the tick itself reads the working branch from HANDOFF on `origin/main`.
- **Next.js 16.4.1 security notice:** the first `npm run build` stops with SecurityFatalError, a retry passes; decide on upgrading. Not blocking.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers for every model (add `strict=True`?). Sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: learning-log draft for 2.3 (autopilot tick, 2026-11-19; earlier: 2.3 slice 5 close-out, PR #26 merged)
- **Committed and pushed; draft PR opened (not merged):** Part 20, ARCHITECTURE decision 20, README, ROADMAP 2.3 ✅, SCIENTIFIC_VALIDATION oscillator section done, step brief `docs/briefs/2.3.md`.
- **Verified:** full `scripts/check.sh --e2e` green on its third run (2872 passed; first runs hit the known Next.js build notice and a sandbox Playwright browser path). Whole-step Opus review: 1 must-fix (half-power points) and 4 overstated claims, all fixed; no second review. CI: not run until the PR exists.
- **Expected:** the start hook prints "Roadmap 🔜: not found" until the merge.
- **Not verified:** the brief's demo was not run in a browser by this tick.

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
