# Autopilot state

Read and updated by every autopilot tick (`.claude/skills/autopilot/SKILL.md`). The author can
edit it too: change `status` to `paused`, or answer a question under "Waiting for you".

status: running
session: session_01KiMGHphJdZSjdXKDzmfkvm
scheduled task: SimForge autopilot, id trig_01D81BmGR4kh1SUbMrdbJi4F (every 4 hours, UTC)
failures: none
branch: claude/laughing-brahmagupta-50jkiy
Authorised phase: Phase 2 (Physics Lab, mechanics and numerical methods), by the author on
2026-10-24. Defaults: the autopilot grills itself and takes its recommended answers.

## Budget (the author may edit these numbers)
- weekly cap: 0.76 (raised from 0.70 by the author on 2026-10-24 for a test tick). A tick never starts if it would take the 7-day window above this. The
  other 30% is kept for the author.
- weekly cap near reset: 0.90. Applies when the 7-day window resets within 12 hours (what is
  left at the reset is lost anyway).
- five-hour cap: 0.50. Above this, the author is probably working: skip.
- starting estimate of a tick's cost: 0.03 of the 7-day window. Replaced by the largest of
  the last three measurements once there are three.

## Measured tick costs (7-day utilisation before → after)
- 2026-10-24 12:44 UTC (test tick 2, planning 1.6): 0.73 → 0.73, under 0.01 at the 1%
  resolution of the readings (5-hour window 0.24 → 0.27). Readings are rounded to 0.01, so
  costs below that show as 0.
- 2026-10-25 04:27 UTC (planning Phase 2 and 2.1, one high-effort subagent): 0.00 → 0.02.
- 2026-10-28 07:23 UTC (planning 2.2, one high-effort subagent): 0.44 → 0.47.
- 2026-10-28 08:27 UTC (2.2 slice 1, builder + reviewer, both high): 0.47 → 0.49.
- 2026-10-28 12:42 UTC (2.2 slice 2, builder + reviewer, both high; long measurements): 0.50 → 0.57.
  Estimated tick cost is now 0.07 (largest of the last three: 0.03, 0.02, 0.07).
- 2026-10-28 16:26 UTC (2.2 slice 3, builder + security reviewer, both high): 0.57 → 0.64.
For scale: on 2026-10-24 a short reply in this session moved the 7-day window by about 0.01.

## Current unit
Roadmap 2.2: slices 1-3 committed. Next: slice 4, the frontend (generic AngleSweepPanel via a
small per-model adapter, the quadratic page, the 1.6 wiring, Vitest, Playwright incl. two
stored-fields cases). Slice 5 (docs) must also fix the plan's D7 wording: Brent can refine
below the first grid step; the 1 µs rule still holds there because of the drag-rate rule.

## Remainder of the current unit
—

## Waiting for you (blocking)
Nothing.

## For your daily review (not blocking)
- Approve or edit the learning-log drafts for PR #12 (journal, 2026-10-25 04:40) and PR #13
  (journal, 2026-10-28 06:50); the autopilot never adds them itself.
- Roadmap question: the capability map lists "best angle against drag strength" and
  "drag-law comparison", which no Phase 2 step schedules. Recommendation: add them to 2.2
  (they reuse the same sweep). Until you answer, 2.2 is built without them.
- Deployment risk (security review of 2.2 slice 3): no rate limit or cap on concurrent sweeps;
  each sweep can hold a worker for ~11 s, so a burst would slow every request. No change made
  (auth and new services are out of scope); decide if it matters for how you run SimForge.
- The weekly cap is 0.76 (your test setting); the default was 0.70.
- Five optional clean-ups from the 2.1 code review (PR #13 description): a bound computed
  twice, duplicated dataclasses/copy code, two re-implemented helpers, duplicated form logic.
