# Autopilot journal

One entry per autopilot tick that did something, newest first. Each lists what was done, the
checks that actually ran, decisions taken without you (with how to reverse them), anything
waiting for you, and the next step. Protocol: `.claude/skills/autopilot/SKILL.md`; current
state: `.claude/autopilot/STATE.md`.

---

## 2026-10-27 ~13:30 UTC: roadmap 2.1 complete (built in chat); autopilot paused
- **Did:** slice 4, the page /physics/projectile/quadratic-drag (5a31773); slice 5, docs
  (plan amendments A1-A11, SCIENTIFIC_VALIDATION, guide Part 18, ARCHITECTURE decision 18,
  README, ROADMAP 2.1 ✅ and 🔜 on 2.2); a docstring correction (cde59bc). Each with a builder
  and a fresh reviewer. Status `waiting-review`; the 4-hourly task is paused.
- **Checks run:** `scripts/check.sh --e2e` on the final code: exit 0 (pytest 1579, Vitest
  211, Playwright 23). Guide excerpts: all three guides ALL OK after the docs review.
- **Decisions taken for you:** the energy legend on the new page says "(constant for the true
  motion)"; the shared Reproducibility component; no drag-law selector (as planned).
- **Waiting for you:** a PR for 2.1.
- **What this means for you:** quadratic drag is in the app, validated against every exact
  special case, with its limits measured.
- **Learning checkpoint:** why is the drag time S a better cost measure than flight time?
- **Next:** after the merge, 2.2 with `grilling` (defaults) then `tdd`.

## 2026-10-25 08:30 UTC: 2.1 slices 1-3 built in chat; paused on the author's "stop after slice 3"
- **Did:** slice 1 reference formulas (ed2d77a), slice 2 integrator and model (74d3164),
  slice 3 API, registry and golden run (d5a4aaa); also enforced 46 test tolerances that
  pytest.approx was loosening (074cf27). Each slice: builder (high effort) + fresh reviewer;
  slice 3's review runs after its commit (the author asked to finish fast). Autopilot paused.
- **Checks run:** slices 1-2: full `scripts/check.sh` passed (pytest 1502). Slice 3: the
  builder's full `scripts/check.sh` passed (pytest 1570); after commit I re-ran 64 API,
  registry and golden tests: passed. Playwright not run for 2.1 yet.
- **Decisions taken for you:** the stiffness guard bounds drag time S = ∫κ|v|dt (proved), not
  the plan's κV·T_bound (which refused 193 of 1007 grid runs that finish); new input rules
  atol ≤ 0.01·min(v₀, v_t) and drag-free flight ≥ 1 µs (both measured); `drag_constant`
  default 0.01 kg/m. All reversible; the plan gets amended in slice 5.
- **Waiting for you:** "continue 2.1" for slices 4-5.
- **What this means for you:** the quadratic-drag model works end to end through the API; there
  is no page for it yet.
- **Learning checkpoint:** why does an explicit solver's step count grow with S?
- **Next:** slice 4 (frontend) with `tdd`, when you say so.

## 2026-10-25 04:40 UTC: Phase 2 split into steps; 2.1 (quadratic drag) planned by default
- **Did:** ROADMAP Phase 2 now has a step table (2.1-2.6, every item of the paragraph in its
  order; 🔜 on 2.1). `docs/plans/ROADMAP_2_1_PLAN.md`: the autopilot grilled itself and took
  its recommended answers. Autopilot commits since your last message: 1 of 6.
- **Usage:** 7-day 0.00 → 0.02 (new week), 5-hour 0.04 at start. One subagent, effort high.
- **Checks run:** none needed (docs only). The plan's formulas were checked numerically by the
  planning subagent against an independent SciPy DOP853 integration (scratch script, not a
  repository test): vertical flight to 5e-11 relative, invariant drift ≤ 3e-10. I re-checked
  its key code claim (projectile runs hash their parameters, `api/routes/physics.py:114`).
- **Decisions taken for you (defaults; reverse any in chat):**
  - a **new model** `physics.projectile.quadratic_drag` and page, not a drag-law option on the
    existing projectile (an option would change every stored projectile run's input hash, so
    replay would refuse them);
  - input `drag_constant` c in kg/m (F = −c|v|v); terminal speed √(mg/c) reported;
  - references: vertical rise (tan) and fall (tanh), terminal speed, energy balance, c → 0
    limit, and a hodograph invariant, the only one that tests the 2-D coupling (a wrong force
    law passed the first four in the subagent's check);
  - existing adaptive solver in a separate integrator (sharing code waits for 2.4);
  - a new learning-guide Part 18; 5 test seams and 5 slices.
- **Waiting for you:** nothing blocking. Review the defaults; a roadmap question in STATE.
- **Draft learning-log entry for PR #12 (add on your approval):**
  ```
  ## Roadmap 1.6: comparison and export
  - **Merged:** PR #12, `82ca0b2` (2026-10-25).
  - **What it does:** pin a reference run and overlay a run of the same model, with a table
    of input and summary changes; recompute a stored run's series (digest-checked); export
    CSV in the browser and a versioned JSON record. Completes Phase 1.
  - **Key concepts:** recompute, don't store (the digest proves a match); RFC 4180 and exact
    number round-trip; CSV formula injection (numbers exempt); relative change undefined at
    a zero reference; tolerances are not significance tests.
  - **Decisions and trade-offs:** CSV made in the browser (covers unsaved runs and uploads);
    reference in the URL, not the database; same-model overlay only; a fresh reviewer per
    slice caught four bugs.
  - **Revisit:** why "not bit-identical" no longer claims a cause.
  - **Next:** Phase 2, starting with 2.1 quadratic drag.
  ```
- **What this means for you:** 2.1 is a *new* model so that every run you already saved still
  replays exactly; the price is a little duplicated solver code until 2.4.
- **Learning checkpoint:** why can't linear drag with any single b match quadratic drag?
- **Next:** 2.1 slice 1 (reference functions) with `tdd`.

## 2026-10-24 21:05 UTC: Phase 2 authorised; self-grilling with defaults; every 4 hours (author)
- **Did:** opened PR #12 (roadmap 1.6) at the author's request. Changed the protocol: a new
  step's design decisions are settled by running `grilling` on itself and accepting its own
  recommended answers (each recorded and reversible); `tdd` seams likewise; the 🔜 may move to
  the next step inside the authorised phase (Phase 2) once the previous PR is merged; an
  authorised phase without a step table is first split into steps, keeping every item and its
  order. Schedule: every 4 hours. Status `running`.
- **Checks run:** none needed (protocol and docs only).
- **Decisions taken for you:** 4 hours rather than 3 (fewer ticks, less usage; reverse in
  chat).
- **Waiting for you:** merge PR #12.
- **What this means for you:** the autopilot no longer waits for you on design choices; you
  review its defaults afterwards in `docs/plans/` and this journal, and can reverse any.
- **Learning checkpoint:** which kinds of decision does it still refuse to take alone, and why?
- **Next:** plan Phase 2 into steps and grill 2.1 (docs only until #12 is merged).

## 2026-10-24 ~20:30 UTC: roadmap 1.6 built in chat (author's session, not a tick)
- **Did:** slices S1-S5 of `docs/plans/ROADMAP_1_6_PLAN.md` and the docs, one commit each
  (8bb7cb7, 25c0d35, d35464c, 4dfc72a, d83c07a, then docs); learning-log entries for PRs
  #9-#11 (32d956c). Each slice: a builder subagent (medium or high effort, same model), then
  a fresh reviewer, then checks here. Status `waiting-review`; the 6-hourly task is paused.
- **Checks run:** `scripts/check.sh --e2e` on the final tree: exit 0; pytest 1234 passed,
  Vitest 195 passed, Playwright 19 passed. Guide excerpts: all three guides ALL OK.
- **Decisions taken for you:** the "not bit-identical" label no longer claims the environment
  differs (nothing checks that); it now says the cause is not checked. `digest_match` is null
  for old records without a digest. Reverse either in `ReferenceRunPanel.tsx` / `outputs.py`.
- **Waiting for you:** a PR for 1.6; the next roadmap step.
- **What this means for you:** every run can now be compared and exported; old runs are
  recomputed and the digest says whether the recomputation is exact.
- **Learning checkpoint:** why are negative numbers exempt from the CSV formula guard?
- **Next:** your choice of the next step, then `grilling` for its decisions.

## 2026-10-24 18:40 UTC: new rule, pick up from the latest conversation (author's request)
- **Did:** the skill's reorient step now reads the session's latest exchange (the author's last
  message and the final response) before choosing work, so a tick continues from work the
  author did in chat between ticks instead of from the previous tick. CLAUDE.md notes it.
  The 18:26 tick was skipped (7-day status `allowed_warning`, 77%).
- **Checks run:** none needed (protocol and docs only).
- **Decisions taken for you:** it reads conversation events back to your last message
  (alternative: only STATE; reverse by deleting the paragraph in step 1.1).
- **Waiting for you:** nothing.
- **What this means for you:** you and the autopilot share one thread of work, so working
  between ticks never makes it redo or undo your session.
- **Learning checkpoint:** why is STATE alone not enough for a tick to know where work stands?
- **Next:** roadmap 1.6, slices S1-S5 (in progress in chat).

## 2026-10-24 12:58 UTC: 1.6 decisions answered; resumed (author's request, not a tick)
- **Did:** recorded the author's answers (yes to all 10, tree confirmed) in the plan and
  STATE; status `running`; 6-hourly task re-enabled (next 18:26 UTC). Work-limit count reset.
- **Checks run:** none needed (docs only).
- **Decisions taken for you:** none.
- **Waiting for you:** merge PR #11; the weekly cap is still 0.76 (your test setting).
- **What this means for you:** the design is settled, so ticks after the merge can build.
- **Learning checkpoint:** why does the plan pin the reference run in the URL, not the database?
- **Next:** after the merge, slice 1 (recompute route) with `tdd`, on a new PR.

## 2026-10-24 12:44 UTC: planned roadmap 1.6 as proposals (test tick 2)
- **Did:** wrote `docs/plans/ROADMAP_1_6_PLAN.md`: what 1.6 builds, 8 decisions with
  recommendations, 5 test-first slices, risks. No code (PR #11 is not merged). Autopilot
  commits since your last message: 1 of 6. Status set to `waiting-review` (nothing else can be
  built until you answer) and the 6-hourly task paused, so waiting costs you nothing.
  Answering the decisions in chat resumes it.
- **Usage:** 7-day 0.73 → 0.73 (under 0.01; readings are rounded to 0.01), 5-hour 0.24 at
  start, 0.27 at the end. One subagent, effort high, same model as this session.
- **Checks run:** none needed (docs only). PR #11 CI on its head: all four jobs green. Three
  of the subagent's claims re-checked in the code (series not stored; Solow's "baseline" and
  "scenario" names; replay's 409 on a version change): all true.
- **Decisions taken for you:** the plan lives in a new `docs/plans/` folder (alternative: in
  this journal; reverse by moving it).
- **Waiting for you:** D1-D8 in the plan; merge PR #11.
- **What this means for you:** the biggest choice is D1: series are not stored, so exports
  of old runs must be recomputed, and the output digest proves the recomputation matches.
- **Learning checkpoint:** why can a CSV cell like `=HYPERLINK(...)` be dangerous, and why
  must the fix leave `-3.2` alone?
- **Next:** your answers, then slice 1 (backend recompute) with `tdd`.

## 2026-10-24 12:32 UTC: resumed, with a one-off test tick (author's request, not a tick)
- **Did:** set STATE `running`, re-enabled the 6-hourly task (next run 18:26 UTC), and
  scheduled one extra test tick for about 12:38 UTC. Added a rule to the skill: subagents
  always inherit this session's model (Opus 5.5); only the effort varies (low, medium, high).
  Changing the model is a proposal for the author. Work-limit count reset to 0 of 6.
- **Usage:** 7-day 72%, 5-hour 21% at 12:26 UTC. The weekly cap is 70% until 14:00 UTC (12 h
  before the 02:00 UTC reset), so the test tick is expected to skip under the budget gate.
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** none.
- **Waiting for you:** merge PR #11; approve the learning-log drafts for PRs #9 and #10.
- **What this means for you:** the test shows the gate working; real work starts on the first
  tick that fits under the cap.
- **Learning checkpoint:** why is a skipped tick still not completely free?
- **Next:** the test tick, then 18:26 UTC: plan roadmap 1.6 as proposals.

## 2026-10-24 12:27 UTC: paused; usage-aware ticks every 6 hours (author's request)
- **Did:** paused the autopilot (scheduled task disabled, STATE `paused`). Changed the schedule
  to every 6 hours. Added a budget gate: each tick reads the author's live 5-hour and 7-day
  usage from this session's events and skips unless it fits under the caps in STATE (7-day
  ≤ 70%, or 90% within 12 h of the weekly reset; 5-hour < 50%). Work is delegated to a
  subagent at an effort level chosen for the job (low, medium or high; never above high).
- **Usage:** 7-day 72%, 5-hour 19% at 12:24 UTC. The 7-day window resets 2026-10-25 02:00 UTC.
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** the caps (70% / 90% / 50%) and the starting cost estimate (3%
  of the week per tick, replaced by measurements). Edit them in STATE's "Budget" section.
- **Waiting for you:** "resume autopilot" when you want it running; merge PR #11.
- **What this means for you:** the autopilot now spends only the part of your weekly allowance
  you are not likely to use, and it learns what a tick really costs.
- **Learning checkpoint:** why may the autopilot use more of the weekly allowance in the 12
  hours before the reset than earlier in the week?
- **Next:** on resume, plan roadmap 1.6 as proposals (no code until PR #11 is merged).

## 2026-10-24 12:20 UTC: autopilot set up (by the author's request, not a tick)
- **Did:** wrote the protocol (`.claude/skills/autopilot/SKILL.md`), this journal and STATE;
  an independent review found 10 weaknesses, all fixed before switching on; created the
  scheduled task "SimForge autopilot" (every 2 hours, into this session).
- **Checks run:** none needed (no code changed).
- **Decisions taken for you:** every 2 hours; a limit of 6 commits without you; your GitHub
  login `Mud0709` is the only source of instructions on GitHub. Change any of these in chat.
- **Waiting for you:** merge PR #11 (green) so 1.6 can start; approve the learning-log drafts
  for PRs #9 and #10.
- **What this means for you:** work continues between your reviews, but nothing merges
  without you, and every decision it took alone is listed here so you can reverse it.
- **Learning checkpoint:** why does the autopilot refuse to start 1.6 on the same PR as 1.5?
- **Next:** plan roadmap 1.6 (comparison and export) as proposals; build once #11 is merged.

