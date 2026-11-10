Last updated: e50a3d4 2026-11-10
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Run-cost rule answered by the author (2026-11-10): an evaluation budget like 2.2's, measured
against the 30 s limit (recorded in the 2.3 plan, slice 3). Next unit: slice 2's worth-doing
review items or slice 3 (its Acceptance block first). Autopilot running.

## Open decisions
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).


## Last task: 2.3 slice 2 built and reviewed (2026-11-10)
- **Author's rule (2026-11-10), after this run:** the test writer and the builder now run in
  the same tick, so red tests are never committed alone (the 2026-11-09 run committed them,
  leaving the branch red for 14 hours). Skill step 4 updated.
- **Done locally and committed/pushed by this run:** `numerical.py`, `model.py`, `schemas.py`; thresholds measured on 1608 runs; docs (SCIENTIFIC_VALIDATION, ARCHITECTURE, plan status). Builder opus high, reviewer opus high.
- **Checks run:** pytest on the two oscillator test files (250 passed), ruff, mypy, doc index. CI: not run (no PR open). Full backend pytest 2338 passed was run by the builder only.
- **Not done:** review items 1-7 (journal 2026-11-10); a false "worst 0.10 / 10x margin" claim was corrected in SCIENTIFIC_VALIDATION.
- **Not in a PR yet;** state: committed and pushed to the working branch.

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
