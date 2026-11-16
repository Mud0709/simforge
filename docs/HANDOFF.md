Last updated: 870b07e 2026-11-15 (learning-log draft written)
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Read the learning-log draft for PRs #20 and #23 (top of `docs/LEARNING_LOG.md`), edit or approve it.
2.3 slice 3 (API, limits, run-cost rule) is built and committed on the working branch (2026-11-16 autopilot); CI not run. A fresh security review found no must-fix (journal 2026-11-16). Next for the autopilot: the worth-doing items (overflow message names Radau for every method), then slice 4 (frontend). The scheduled task's branch on claude.ai is still yours to fix.

## Open decisions
- **Learning-log draft for PR #20 and #23:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Scheduled task branch (your clicks):** `update_trigger` cannot change a task's repo or branch (it edits only name, schedule, enabled, model, prompt). Stored: repo `Mud0709/simforge`, push-outcome branch `claude/serene-feynman` (wrong), model Sonnet 5.5, disabled, one-line prompt. Set the branch to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming; the tick itself reads the working branch from HANDOFF on `origin/main`.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers for every model (add `strict=True`?). Sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: 2.3 slice 3 (autopilot, 2026-11-16)
- **Done locally, committed, pushed (no PR yet):** `/api/v1/physics/oscillator/simulate`, `ModelEntry`, one appended golden entry, `MAX_RUN_RHS_EVALUATIONS = 400,000` counted inside the RHS (Radau Jacobian included; slowest budgeted run 11.7 s on the builder's machine), and SciPy's Radau Jacobian overflow turned into a 422. **Verified by the tick:** full backend `pytest -q -W error` 2565 passed; ruff, format, mypy clean; golden diff OK; protected test hashes unchanged. **Not run:** `scripts/check.sh --e2e`, a separate `/security-review`, a second `make api-types`.
- **Fresh review (Opus):** no must-fix. Worth doing: the `api/errors.py` comment says "Python form" but writes e.g. `1000000.0` (changes bound wording for every model); the limits test's `str(bound) in msg` is self-referential (a protected test file); the overflow message blames Radau for every method; the DOP853 energy-balance observation is unverified.
- **Decisions taken for you:** stored summary adds `initial_displacement`; the overflow is a 422, not an analytic Jacobian (that would change Radau numerics).

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
