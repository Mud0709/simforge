Last updated: 49375c5 2026-11-10 (plus the review-fix PR's commits)
Working branch: claude/laughing-brahmagupta-50jkiy
<!-- Overwrite after each meaningful task (skill simforge-status). Keep these headings: the
start hook prints "Next action" and "Open decisions"; the fresh-session autopilot reads
"Working branch" from this file on main. Mark an open decision "(blocks: <unit>)" only if
it stops that unit; answer one by adding a line starting "Answer:" under it. A chat on any
other branch is warned by the start brief and shown this file from origin/<working branch>. -->

# SimForge handoff

## Next action
Review and merge the review-fix PR (branch `claude/scientific-review-process-sync-3t3aku` into
this working branch; CI runs on it). Then 2.3 slice 3, starting with its Acceptance block and
the evaluation budget. Autopilot is running: its 12:59 UTC tick must not redo these fixes
(STATE "Current unit" says so); if the PR is still open then, say "pause autopilot".

## Open decisions
- **Confirm (taken on your "fix all", reversible):** quadratic drag and its sweep are now v1.0.1 (a threshold that cannot fail gives no verdict); stored v1.0.0 runs of those two models can no longer be replayed (409, version changed). To reverse: set both versions back and re-pin `tests/api/golden_runs.json`.
- Autopilot: weekly cap 0.76 (test) or back to 0.70? Used only when a run can read usage (rarely).
- Roadmap: "best angle against drag strength" and "drag-law comparison" are in the capability map but no Phase 2 step (recommend: schedule them; nothing built).
- Deployment risk: no rate limit or concurrency cap on sweeps (~11 s each); matters only if SimForge is ever public.
- Replay: should differing step counts be informational rather than "differs"?
- Oscillator energy check: normalise by the energy in motion instead of kX² (it is ~800x loose for slow motions)? Not blocking.
- 2.4: keep the exact-vs-numerical table beside the new checks on the three Phase 0 pages (recommended: yes; `docs/plans/ROADMAP_2_4_NOTES.md`).
- Not blocking: five optional clean-ups from the 2.1 review (PR #13 description).

## Last task: review fixes (2026-11-10, chat session at the author's request)
- **Must-fix 1, done:** quadratic drag, its sweep and the oscillator report `passed = null` with an "uninformative" note when a threshold allows an error above 100%; a sweep aggregate is failed > no verdict > passed. Versions 1.0.1, two golden digests re-pinned.
- **Must-fix 2 and 3, done:** with F0 = 0 the drive frequency limits nothing (cycles, minimum duration, 100 w0 rule); displacement floor 5e-9 from the measured corner (DOP853 7.33e-10 of X).
- **Worth-doing, done:** slice 2 items 3, 5, 6, 7 (free-decay thresholds count cycles to the second maximum, re-measured on 1680 decays; the resonance curve contains its peak; a `free_decay_not_checked` row; X-is-a-bound limitation); SCIENTIFIC_VALIDATION's stale replay and model counts (seven models, eight cases: the earlier handoff's "registry has 8" meant cases); `scripts/check_excerpts.py` in `scripts/check.sh` and the backend tests (it caught a moved excerpt during this work); STATE "Current unit".
- **Not done:** slice 2 item 1 (worst-case run times) stays with slice 3's evaluation budget; measured for it: Radau, 500 cycles at w = 100 w0, 792 s (tightest pair), 133 s (default). Finding 7 (checks for the three Phase 0 models) is planned, not built: `docs/plans/ROADMAP_2_4_NOTES.md`. Finding 8 (literature check) left, as asked.
- **Checks run locally:** backend ruff, ruff format, mypy, full pytest (2373 passed), docs index, excerpts (71 match), OpenAPI export (no change). **Not run locally:** frontend checks and Playwright (no frontend file changed); CI runs them on the PR.
- **State:** committed and pushed to the review branch; PR into the working branch open (draft); not merged.

## Learning handoff
- **What it does:** a per-run check now has three outcomes, pass, fail or no verdict; "no verdict" is used when the threshold is so loose that the check could not fail.
- **Why it matters:** a green tick is a claim. If the test could not have come out red, the tick claims something that was never tested.
- **Key concept:** a threshold is only informative if a wrong answer could exceed it; here residuals are fractions, so a threshold above 1 allows a 100% error.
- **Trade-off:** changing what a response says (even only `passed`) is an output change, so the models became v1.0.1 and old stored runs of them no longer replay.
- **You should be able to explain:** why the oscillator's cycle count ignores the drive frequency when F0 = 0, and why the free-decay thresholds no longer grow with the length of the run.
