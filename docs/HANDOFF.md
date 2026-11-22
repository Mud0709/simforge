Last updated: 6f0b7f4 2026-11-22 (2.5 plan tick)
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
**2.5 (Generic sweeps) is planned and reviewed** (`docs/plans/ROADMAP_2_5_PLAN.md`, 6 slices; 3 reviews, must-fix applied). Next autopilot tick: build tick for all slices. Nothing is built; PR not opened; CI not run (no PR). Your A2 sitting runs alongside (`docs/LOCAL_PAIRING.md`); fetch before you push.
Known red: `backend/tests/physics/foundations/test_core_momentum.py`, 6 failures until you write `momentum` (yours; the 2.5 PR opens only once they pass). Set to `Known red: none` when done.

## Open decisions
- **2.5 plan, your call (not blocking):** D1/D5 treat `numerics/` and `physics/sweep_checks.py` as exempt from CLAUDE.md's "two labs" rule (as 2.4 did); the simulated resonance curve is the second user (a 2.3-plan suggestion). Confirm or redirect before the build tick if you disagree.
- **A2 confirmed (2026-11-21):** all four answered yes in chat (division of labour; A2 before 2.5, parked by default three weeks after S0, extendable once; SL+HL in one PR; syllabus lines). If you have not yet compared the plan's "Syllabus re-check" lines with your Physics guide copy, do it before sitting 2.
- **Learning-log drafts for PR #20, #23, #26 and #27:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Next.js 16.4.1 security notice:** the first `next build` in `scripts/check.sh` now stops on it every run, because the backend runs past the notice's 5-minute retry window; a retry passes. Upgrading Next.js is a dependency change: your call (recommended: upgrade in its own PR). Not blocking.
- **Further time-stepping models on the workbench:** damped/driven oscillator and quadratic-drag fixed-step studies are not in 2.4; Phase 2's done-when now names Phase 4's long-run integrator comparison (orbits) for further models (recommended: schedule the oscillator ones with 2.5 or Phase 4). Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them).
- Ruleset on `main`: "Require status checks" has no checks selected; branch clean-up (`backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`). Your clicks; not blocking.
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers (add `strict=True`?); sweep rate limit; replay "differs" for step counts; five clean-ups from the 2.1 review (PR #13); the 2.4 worth-doing list in `docs/journal/2026-11-19-1207-2-4-plan-and-build.md`.

## Last task: 2.5 plan tick (autopilot, 2026-11-22)
- **Committed and pushed to the working branch (no PR):** 🔜 moved to 2.5; 2.4 step cost; plan with 3 reviews (journal `docs/journal/2026-11-22-1110-2-5-plan.md`). Must-fix: phase bound arcsin, phase wrapping, corner-grid cycle cap (Q limit about 300). **Not verified:** the plan's cycle-cap estimates (slice 3 measures).

## Learning handoff
- **What it does:** one driver in `numerics/` runs any fixed-step study; the oscillator and the projectile plug in their exact solutions and checks.
- **Key concept:** a symplectic method keeps a slightly different energy H̃ exactly constant, so the true energy wobbles but never drifts. Measure order over every step, not one period: symplectic Euler looks second order at t = T because its first-order error cancels there.
- **Trade-off:** each check's threshold is measured (1-2-5, ≥ 10× the worst), so it is evidence, not proof; near θ = 2 the rounding is magnified by H̃'s conditioning, and the check scales for it.
