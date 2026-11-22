# Autopilot state

Read and updated by every autopilot tick (`.claude/skills/autopilot/SKILL.md`). The author can
edit it too: set `stop:` to `none` to clear a stop, or add a line starting `Answer:` under an
item in "Open decisions" of `docs/HANDOFF.md`. On/off is not here: it is the scheduled task's
enabled flag only (skill step 6).

stop: none (the other values, set by a tick: `blocked`, `waiting-review`)
scheduled task: SimForge autopilot (fresh session), id trig_01LWbTdfvYfXswNkcewkKTUU (a fresh
  session per run, repository attached, auto-fix off, model per the `CLAUDE.md` table; three times a day at
  02:59, 10:59 and 18:59 UTC, `59 2,10,18 * * *`, since 2026-11-22; was twice a day from 2026-11-03). The old task
  trig_01D81BmGR4kh1SUbMrdbJi4F (bound to one session) is disabled and kept; never re-enable it.
work limit from: bcf6518
ladder rung: none (the retry ladder by model, skill step 4)
failures: none
branch: see the `Working branch:` line of `docs/HANDOFF.md` on `origin/main`.
Authorised phase: Phase 2 (Physics Lab, mechanics and numerical methods), by the author on
2026-10-24. Plans: checked by fresh reviewers as `CLAUDE.md` says, must-fix findings only
(since 2026-11-07; before, the autopilot accepted its own defaults).

## Budget (the author may edit these numbers)
- unit of work: one phase of a roadmap step for all its slices: a plan tick, a build tick, then
  a review-and-fix tick (the author's rule of 2026-11-22, replacing plan-then-build of
  2026-11-19). Caps: 4 working subagents per slice across the step and 24 per tick, 5 Haiku
  helper spawns per slice per tick, 12 commits between work-limit resets (skill steps 0b and 4).
- working runs per day: 3 (the author's rule of 2026-11-22; was 2 from 2026-11-03, 1 before). Days run 24 h from 02:00 UTC.
  Counted in git from `Autopilot-run: work` commits, because a fresh session cannot read live
  usage. This replaces the 0.08 daily allowance, which needed live readings. The weekly and
  five-hour usage caps were removed on 2026-11-15: no scheduled run can read usage.

## Measured tick costs, historical (7-day utilisation before → after; readings existed only in sessions that could read usage)
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
- 2.3 (PR #26): 10 journalled autopilot ticks 2026-11-09 to 2026-11-19 for slices 2-5 plus
  chat sessions for planning, slice 1 and the slice 2 review (not counted); subagents by agent,
  rungs and usage unknown (no usage readings in fresh sessions).

## Current unit
Roadmap 2.4: planned (self-grilled at the author's request, 3 reviews) and built in one chat
session on 2026-11-19, slices 1-5, each risky slice reviewed, whole-step review done, full
check run (Next.js build notice: retry passed). Draft PR opened for the author's review.
The work limit (12 commits since bcf6518) is reached with the close-out commit; the next
tick waits for the merge (skill step 2.5), then resets the limit at the merge.

Back on the main line (the author, 2026-11-22): 2.4's PR #27 is merged. Next: Track B 2.5
(Generic sweeps): move 🔜 to 2.5, add the 2.4 step-cost line, reset the work limit at the
merge, then the 2.5 plan tick. Track A2 is the author's own local work: hands off (skill step
4, "Known-red tests").

## Remainder of the current unit
None: 2.4 finished and merged (PR #27).

## Waiting for you
Open decisions and pending learning-log drafts live only in `docs/HANDOFF.md` ("Open
decisions"), since 2026-11-02. This file keeps the autopilot's own state.
