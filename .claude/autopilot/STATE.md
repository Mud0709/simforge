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
For scale: on 2026-10-24 a short reply in this session moved the 7-day window by about 0.01.

## Current unit
Roadmap 2.2 (angle sweeps for both drag laws), 🔜 in ROADMAP.md. Roadmap 2.1 is merged (PR #13,
646e996, 2026-10-28). First unit: plan 2.2 by running `grilling` on yourself with defaults
into `docs/plans/ROADMAP_2_2_PLAN.md`, then build it with `tdd` on a new PR (ask the author
before opening it). Scope: exactly the 2.2 row; the two capability-map items below stay out
unless the author says otherwise.

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
- The weekly cap is 0.76 (your test setting); the default was 0.70.
- Five optional clean-ups from the 2.1 code review (PR #13 description): a bound computed
  twice, duplicated dataclasses/copy code, two re-implemented helpers, duplicated form logic.
