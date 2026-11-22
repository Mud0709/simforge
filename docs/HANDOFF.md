Last updated: 717c2c3 2026-11-22 (autopilot back on, Track B 2.5; new tick shape)
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
**Autopilot is back on, on Track B (2026-11-22):** three ticks a day (02:59, 10:59, 18:59 UTC). Its first tick moves 🔜 to 2.5 (Generic sweeps), adds the 2.4 step-cost line and plans 2.5; then a build tick, then a review-and-fix tick. **Your A2 sitting 0** is unchanged and runs alongside, in your local session (`docs/LOCAL_PAIRING.md`, `docs/FOUNDATIONS_CODING_GUIDE.md` chapters 0-5, chapter 9's `momentum`; test commit `a6e9f5f`). Fetch before you push: the autopilot pushes to the same branch.
Known red: `backend/tests/physics/foundations/test_core_momentum.py`, 6 failures until you write `momentum` (yours; the autopilot never touches `physics/foundations/collisions/`, and opens the 2.5 PR only once they pass). Set this line to `Known red: none` when done.

## Open decisions
- **Scheduled task branch (your clicks), still open:** the task's stored push-outcome branch is `claude/serene-feynman` (wrong); `update_trigger` cannot change it. Set it to `claude/laughing-brahmagupta-50jkiy` in the task's settings (claude.ai, Routines). Ticks still switch to the branch from this file, so this is not blocking, but fix it soon.
- **A2 confirmed (2026-11-21):** all four answered yes in chat (division of labour; A2 before 2.5, parked by default three weeks after S0, extendable once; SL+HL in one PR; syllabus lines). If you have not yet compared the plan's "Syllabus re-check" lines with your Physics guide copy, do it before sitting 2.
- **Learning-log drafts for PR #20, #23, #26 and #27:** read it, edit or approve (remove the DRAFT tag). Not blocking.
- **Next.js 16.4.1 security notice:** the first `next build` in `scripts/check.sh` now stops on it every run, because the backend runs past the notice's 5-minute retry window; a retry passes. Upgrading Next.js is a dependency change: your call (recommended: upgrade in its own PR). Not blocking.
- **Further time-stepping models on the workbench:** damped/driven oscillator and quadratic-drag fixed-step studies are not in 2.4; Phase 2's done-when now names Phase 4's long-run integrator comparison (orbits) for further models (recommended: schedule the oscillator ones with 2.5 or Phase 4). Not blocking.
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them).
- Ruleset on `main`: "Require status checks" has no checks selected; branch clean-up (`backup/main-before-rewrite`, `backup/branch-before-rewrite`, `claude/epic-sagan-30vpv3`). Your clicks; not blocking.
- Not blocking, your call: `StrictModel` accepts `true` and `"2"` as numbers (add `strict=True`?); sweep rate limit; replay "differs" for step counts; five clean-ups from the 2.1 review (PR #13); the 2.4 worth-doing list in `docs/journal/2026-11-19-1207-2-4-plan-and-build.md`.

## Last task: autopilot back on, new tick shape (chat session, 2026-11-22)
- **Done locally, then committed and pushed to the working branch (no PR, a procedure edit):** ticks now do one kind of work for all slices: plan, build (no reviews, no debugging; a failing slice is deferred), then review-and-fix (debugging, every slice review plus the whole-step review together, fixes, full check, PR). Three working runs a day. `builder` and `test-writer` (Sonnet 5.5) now run at high effort; Opus agents stay medium, Haiku helpers high.
- **Your answers recorded:** A2's red tests are known-red and hands-off (skill step 4); a slice failing in a build tick is deferred to the review-and-fix tick.
- **Task:** enabled, `59 2,10,18 * * *`. **CI:** not run (no PR). **Not verified:** a real tick under the new shape.

## Learning handoff
- **What it does:** one driver in `numerics/` runs any fixed-step study; the oscillator and the projectile plug in their exact solutions and checks.
- **Key concept:** a symplectic method keeps a slightly different energy H̃ exactly constant, so the true energy wobbles but never drifts. Measure order over every step, not one period: symplectic Euler looks second order at t = T because its first-order error cancels there.
- **Trade-off:** each check's threshold is measured (1-2-5, ≥ 10× the worst), so it is evidence, not proof; near θ = 2 the rounding is magnified by H̃'s conditioning, and the check scales for it.
