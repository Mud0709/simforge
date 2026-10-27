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
Roadmap 2.1: slices 1-3 committed (ed2d77a, 74d3164, d5a4aaa); slice 3's fresh-context review
was still running at the pause, its fixes to be committed as a follow-up. On 2026-10-27 the
author said "continue 2.1 slices 4-5": slices 4 (frontend) and 5 (docs) are being built in chat.

## Remainder of the current unit
—

## Waiting for you (blocking)
Nothing.

## For your daily review (not blocking)
- PR #12 is merged: a learning-log draft for 1.6 is in the journal entry of 2026-10-25 04:40.
- Review the 2.1 defaults in `docs/plans/ROADMAP_2_1_PLAN.md`; reverse any in chat.
- Roadmap question: the capability map lists "best angle against drag strength" and
  "drag-law comparison", but no Phase 2 step schedules them. Add them to 2.2?
- The weekly cap is 0.76 (your test setting); the default was 0.70.
