# Autopilot state

Read and updated by every autopilot tick (`.claude/skills/autopilot/SKILL.md`). The author can
edit it too: change `status` to `paused`, or answer a question under "Open decisions" in `docs/HANDOFF.md`.

status: waiting-review
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
- daily allowance: 0.08 of the 7-day window per day (set by the author on 2026-10-29). Days
  run 24 h from 02:00 UTC; the week starts Sunday 02:00 UTC (the seven-day reset). Counts only
  the autopilot's measured tick costs dated that day; the weekly cap applies on top.
- notifications: one push per day (summary of the previous day) and one whenever the
  autopilot stops for the author or reaches the daily allowance. Last daily summary: 2026-10-30 (for 2026-10-29).
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
- 2026-10-28 20:27 UTC (2.2 slice 4, builder + reviewer, both medium): 0.64 → 0.68.
- 2026-10-29 00:27 UTC (2.2 slice 5, docs writer + reviewer, both medium; full e2e check): 0.69 → 0.74.
For scale: on 2026-10-24 a short reply in this session moved the 7-day window by about 0.01.

## Current unit
None. Roadmap 2.2 is merged (PR #14, `0ea819a`); 🔜 is on 2.3 (oscillators), not started.

## Remainder of the current unit
—

## Waiting for you
Open decisions and pending learning-log drafts live only in `docs/HANDOFF.md` ("Open
decisions"), since 2026-11-02. This file keeps the autopilot's own state.
