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
For scale: on 2026-10-24 a short reply in this session moved the 7-day window by about 0.01.

## Current unit
Plan Phase 2: split its ROADMAP paragraph into steps (every item, same order, 🔜 on 2.1), then
grill 2.1's design decisions with defaults into `docs/plans/ROADMAP_2_1_PLAN.md`. Docs and plan
only, no code, until PR #12 (roadmap 1.6) is merged; then build 2.1 with `tdd` on a new PR.

## Remainder of the current unit
—

## Waiting for you (blocking)
Nothing.

## For your daily review (not blocking)
- Merge PR #12 (roadmap 1.6). After the merge, approve or edit the 1.6 learning-log draft.
- The weekly cap is 0.76 (your test setting); the default was 0.70.
