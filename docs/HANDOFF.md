Last updated: 4413a2f 2026-11-09
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Velocity scale answered by the author (2026-11-09): **V = ω₀X** (recorded in the 2.3 plan's
slice 2 Acceptance block). Autopilot resumed; its next unit is the slice 2 test writer.

## Open decisions
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: the first resumed run checked; trailer and journal-time fixes (2026-11-09)
- **The run** (session `cse_01DMcXP259w3PPwfxsRAipcx`, 12:03-12:09 UTC, $1.91): added slice
  2's Acceptance block (Opus planner, reviewer (c) on Opus: 2 must-fix applied, 9 worth-doing
  listed), regenerated the index, wrote the first `docs/journal/` entry, stopped on the
  velocity-scale decision (correctly), and could not pause itself (`update_trigger` not
  callable), so the author's session paused it. Commit `10db2a9` is on this working branch
  only; `autopilot-work` was the run's local label, and GitHub has only `main` and this branch.
- **Fixed:** `.githooks/commit-msg` now moves a stray `Autopilot-run:` line into the final
  trailer block (tested on six layouts: the `10db2a9` layout, correct ones, no co-author,
  plain, a body mention kept, a merge); the skill and the journal template take the entry's
  time from `date -u` just before the commit. Findings recorded in `.claude/autopilot/FINDINGS.md`.
- **Checks run:** shellcheck on the hook (exit 0); the six-layout commit test; the run-count
  grep still finds every work commit; `doc_index.py --check`. CI: not run (no PR).
- **State:** committed and pushed to this branch; not in a PR yet (no PR open). Autopilot
  resumed (STATE `running`, task enabled; schedule 02:59 and 12:59 UTC).

## Learning handoff
- **What it does:** sessions load a short map and open one section of a large document by its
  line range; the autopilot's journal is one small file per run whose numbers come from a script.
- **Why it matters:** reading a 256 KB guide to use one chapter costs ten times the tokens;
  numbers a model types can be wrong, numbers a parser reads from tool output cannot drift.
- **Key concept:** an index (a map from topic to location) trades a little upkeep (regenerating
  it, enforced by a check) for much cheaper lookups.
- **Trade-off:** every edit to a large document now also regenerates the index, or CI fails.
- **You should be able to explain:** why the startup context barely changed while per-task
  reading fell by about ten times.
