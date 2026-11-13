# Autopilot state

Read and updated by every autopilot tick (`.claude/skills/autopilot/SKILL.md`). The author can
edit it too: change `status`, or add a line starting `Answer:` under an item in "Open
decisions" of `docs/HANDOFF.md`. While the task is paused, an answer takes effect only once
the author says "resume autopilot" (which also resets `work limit from:`).

status: paused
scheduled task: SimForge autopilot (fresh session), id trig_01LWbTdfvYfXswNkcewkKTUU (a fresh
  session per run, model Sonnet 5.5, repository attached, auto-fix off; twice a day at 02:59
  and 12:59 UTC, `59 2,12 * * *`, since 2026-11-03). The old task
  trig_01D81BmGR4kh1SUbMrdbJi4F (bound to one session) is disabled and kept; never re-enable it.
work limit from: 8e7596e
ladder rung: none (the builder's effort ladder, skill step 4)
failures: none
branch: see the `Working branch:` line of `docs/HANDOFF.md` on `origin/main`.
Authorised phase: Phase 2 (Physics Lab, mechanics and numerical methods), by the author on
2026-10-24. Plans: checked by one fresh reviewer (three for the scientific core, since 2026-11-13),
must-fix findings only (since 2026-11-07; before, the autopilot accepted its own defaults).

## Budget (the author may edit these numbers)
- working runs per day: 2 (the author's rule of 2026-11-03; was 1). Days run 24 h from 02:00 UTC.
  Counted in git from `Autopilot-run: work` commits, because a fresh session cannot read live
  usage. This replaces the 0.08 daily allowance, which needed live readings.
- Used only when a run can read live usage (see the skill, 0b.2): weekly cap 0.76 (raised from
  0.70 by the author on 2026-10-24 for a test tick); weekly cap near reset 0.90 (within 12 h
  of the 7-day reset); five-hour cap 0.50.
- notifications: one push per run (skill step 7).

## Measured tick costs (7-day utilisation before → after; only when readable)
- 2026-10-24 12:44 UTC (test tick 2, planning 1.6): 0.73 → 0.73, under 0.01 at the 1%
  resolution of the readings (5-hour window 0.24 → 0.27). Readings are rounded to 0.01, so
  costs below that show as 0.
- 2026-10-25 04:27 UTC (planning Phase 2 and 2.1, one high-effort subagent): 0.00 → 0.02.
- 2026-10-28 07:23 UTC (planning 2.2, one high-effort subagent): 0.44 → 0.47.
- 2026-10-28 08:27 UTC (2.2 slice 1, builder + reviewer, both high): 0.47 → 0.49.
- 2026-10-28 12:42 UTC (2.2 slice 2, builder + reviewer, both high; long measurements): 0.50 → 0.57.
  Estimated tick cost is now 0.07 (largest of the last three: 0.03, 0.02, 0.07).
- 2026-10-28 16:26 UTC (2.2 slice 3, builder + security reviewer, both high): 0.57 → 0.64.
- 2026-10-28 20:27 UTC (2.2 slice 4, builder + reviewer, both medium): 0.64 → 0.68.
- 2026-10-29 00:27 UTC (2.2 slice 5, docs writer + reviewer, both medium; full e2e check): 0.69 → 0.74.
For scale: on 2026-10-24 a short reply in this session moved the 7-day window by about 0.01.

## Step costs (one line per merged roadmap step; unknown parts written "unknown")
- 2.2 (PR #14): 7-day usage 0.44 → 0.74 (about 0.30 of a week) over 6 ticks: planning plus 5
  slices, builder and reviewer per slice (high, then medium); measured from usage readings.

## Current unit
Roadmap 2.3: slice 1 (exact solution) done in 4882fc4. Next: slice 2 (numerical solve and run),
on hold by the author. Under the 2026-11-07 rules its first unit is to add slice 2's Acceptance
block (planner, checked by reviewer (c)); the plan has none yet.

## Remainder of the current unit
Slices 2-5 of `docs/plans/ROADMAP_2_3_PLAN.md`.

## Waiting for you
Open decisions and pending learning-log drafts live only in `docs/HANDOFF.md` ("Open
decisions"), since 2026-11-02. This file keeps the autopilot's own state.
