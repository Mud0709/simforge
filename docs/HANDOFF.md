Last updated: 2.4 close-out 2026-11-19
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Track A module A2 (momentum and collisions) is planned (`docs/plans/TRACK_A_A2_PLAN.md`, three reviews applied) and its coding guide is written (`docs/FOUNDATIONS_CODING_GUIDE.md`, chapters 0-12); committed and pushed to the working branch (3f20c95), no PR (plan and docs only). Confirm the four A2 questions below; then Claude starts S0 (stubs and the first test on a new A2 branch) and you do sitting 0 on your laptop.

## Open decisions
- **A2 confirmations (blocks: A2 S0):** (1) division of labour: you write 13 core functions in five sittings, Claude writes tests first and everything else; (2) A2 before 2.5: Track B pauses while A2 is the working branch, parked by default three weeks after S0 unless extended once; (3) SL and HL in one PR; (4) re-check the plan's "Syllabus re-check" A.2 lines against your Physics guide copy.
- **Learning-log drafts for PR #20, #23, #26 and #27:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Next.js 16.4.1 security notice:** the first `next build` in `scripts/check.sh` now stops on it every run, because the backend runs past the notice's 5-minute retry window; a retry passes. Upgrading Next.js is a dependency change: your call (recommended: upgrade in its own PR). Not blocking.
- **Scheduled task branch (your clicks):** stored push-outcome branch `claude/serene-feynman` (wrong); set it to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines) before resuming. The task is disabled.
- **Further time-stepping models on the workbench:** damped/driven oscillator and quadratic-drag fixed-step studies are not in 2.4; Phase 2's done-when now names Phase 4's long-run integrator comparison (orbits) for further models (recommended: schedule the oscillator ones with 2.5 or Phase 4). Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them).
- Ruleset on `main`: "Require status checks" has no checks selected; branch clean-up (`backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`). Your clicks; not blocking.
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers (add `strict=True`?); sweep rate limit; replay "differs" for step counts; five clean-ups from the 2.1 review (PR #13); the 2.4 worth-doing list in `docs/journal/2026-11-19-1207-2-4-plan-and-build.md`.

## Last task: roadmap 2.4 planned and built (chat session, 2026-11-19)
- **Pushed; draft PR #27 open (not merged):** plan (self-grilled, 3 reviews), slices 1-5, docs (Part 21, brief, ARCHITECTURE 21, SV, README, ROADMAP ✅).
- **Verified:** every slice's Acceptance; full pytest 3295 passed; `check.sh --e2e` all green except the first `next build` (Next.js notice; retry passed), Playwright 37 passed. Reviews: 1 must-fix in slice 2, fixed; whole-step review no must-fix.
- **CI:** not checked yet. **Not verified:** the brief's demo in a browser.
- **Work limit:** 12 commits since bcf6518 (reached); it resets at the merge.

## Learning handoff
- **What it does:** one driver in `numerics/` runs any fixed-step study; the oscillator and the projectile plug in their exact solutions and checks.
- **Key concept:** a symplectic method keeps a slightly different energy H̃ exactly constant, so the true energy wobbles but never drifts. Measure order over every step, not one period: symplectic Euler looks second order at t = T because its first-order error cancels there.
- **Trade-off:** each check's threshold is measured (1-2-5, ≥ 10× the worst), so it is evidence, not proof; near θ = 2 the rounding is magnified by H̃'s conditioning, and the check scales for it.
