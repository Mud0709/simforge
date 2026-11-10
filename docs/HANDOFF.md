Last updated: 7e7ce40 2026-11-10 (plus the review's open decisions below)
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
- **Must-fix (review 2026-11-10), quadratic drag and its sweep: checks that cannot fail are shown as passed.** Thresholds are `1e4 x accuracy + 1e-9`, and `rtol` may be up to 1e-3, so at rtol >= 1e-4 every threshold is >= 1 (run: rtol 1e-3 gives energy threshold 10 x E0 and "speed <= proved bound" passing up to 11 x the bound; with atol 0.1, 60 to 80). No note says so; the oscillator already labels this "uninformative". Options: (a) the oscillator's note, same wording; (b) `passed = null` (informational) when the threshold exceeds 1; (c) lower the largest rtol. Recommend (a)+(b). Either changes outputs, so it also needs: bump both models to v1.0.1 and re-pin the two golden digests (recommended), or keep v1.0.0 as PRs #8/#9 did.
- **Must-fix before the oscillator endpoint (blocks: 2.3 slice 3; the fix unit itself is not blocked).** Two slice 2 review items change what users are told or allowed: item 4, the drive frequency still counts when F0 = 0 (`schemas.py:98`, cycles = T max(w0, w)/2pi), so a free run is refused or its thresholds loosened by a number that has no physical effect (recommend: use w0 alone when F0 = 0, with a test); item 2, the displacement floor 1e-9 has a 4.6x margin at an unmeasured corner, which SCIENTIFIC_VALIDATION already promises to measure "before slice 3" (recommend: measure the tightest-pair, 500-cycle, w = 100 w0 corner for all three methods and re-justify or raise the floor). Items 1, 3, 5, 6, 7 are worth doing, not blocking.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).


## Review of the scientific core and SCIENTIFIC_VALIDATION.md (2026-11-10, no code changed)
- **Verified by running:** full backend pytest on 7e7ce40, 2338 passed; documented test counts (317, 84, 166, 226) match; all 71 learning-guide excerpts match their source lines.
- **Re-derived by hand, no error found:** linear-drag closed forms and Lambert W; quadratic R1-R8 (hodograph invariant, both bounds, drag-time bound); the sweep's RS3 coefficients and `u`; Solow rho, golden rule, k* range; the oscillator's transient, six caps of X and scaled works.
- **Worth doing (docs out of step, no wrong number):** SCIENTIFIC_VALIDATION "Reproducibility" still says cases 7 and 8 ran only locally and "All six models (seven cases)" (the registry has 8; CI has run them since PRs #13/#14); `.claude/autopilot/STATE.md` "Current unit" still waits for the run-cost answer given in 7e7ce40; the "Learning handoff" below describes PR #17, already logged; the excerpt check is not in `scripts/check.sh`.

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
