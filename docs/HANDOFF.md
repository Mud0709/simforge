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
Then 2.3 slice 3: its Acceptance block is written and reviewed (2026-11-15 autopilot); the build is next. The scheduled task's branch on
claude.ai is still yours to fix (first open decision). PR #24 is merged into the working branch.

## Open decisions
- **Learning-log draft for PR #20 and #23:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Scheduled task branch (your clicks):** `update_trigger` cannot change a task's repo or branch (it edits only name, schedule, enabled, model, prompt). Stored: repo `Mud0709/simforge`, push-outcome branch `claude/serene-feynman` (wrong), model Sonnet 5.5, disabled, one-line prompt. Set the branch to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming; the tick itself reads the working branch from HANDOFF on `origin/main`.
- Ruleset on `main`: "Require status checks" has no checks selected (add `Backend (ruff, mypy, pytest)`, `Frontend (eslint, prettier, tsc, vitest, build)`, `API contract in sync`, `End-to-end (Playwright)`). Branch clean-up (your clicks): `backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`. Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them). 2.4: keep the exact-vs-numerical table beside the new checks (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking: sweep rate limit (matters only if public); replay "differs" for step counts; oscillator energy check normalisation; five clean-ups from the 2.1 review (PR #13).

## Last task: one on/off switch for the autopilot (author's request, 2026-11-15)
- **Done locally, committed and pushed (PR #24, not merged):** the scheduled task's `enabled` flag is the only on/off control ("pause autopilot" = `update_trigger enabled:false`, "resume" = `enabled:true`, no commit or PR). STATE no longer has `status`; it has `stop: none|blocked|waiting-review` (set only by a tick) plus its counters. SKILL.md steps 0b.0, 1.2, 4, 5, 6 and the instructions rule, and `CLAUDE.md`'s Autopilot paragraph, match.
- **Done outside git:** task `trig_01LW…` enabled via `update_trigger`; next tick 2026-11-16 02:59 UTC.
- **Verified:** `backend/tests/scripts` 111 passed (no test names `status`); CI on the PR: see its checks. **Not enforceable:** that only your words flip the flag (nothing stops another session from calling `update_trigger`; the skill says it is yours).
- **Still yours:** the task's push-outcome branch on claude.ai shows `claude/serene-feynman`; I cannot change it. After a stop (`blocked`/`waiting-review`), "resume autopilot" enables the task and the next tick clears the stop only if you have also answered (`stop: none`, an `Answer:` line or a comment).

## Learning handoff
- **What it does:** each agent's model and effort are written in its own file, and hooks stop an agent doing what its role forbids.
- **Key concept:** a rule in prose is a request; a rule in a hook is a fact. The tests found a real bug (`sed -i` slipped through).
- **Trade-off:** more CLAUDE.md text costs tokens in every session, so each rule lives in one place and the rest point to it.
