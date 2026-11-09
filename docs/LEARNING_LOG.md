# SimForge learning log

One short entry per merged milestone, newest first: what was built, what it taught, and what
to revisit. Detail lives in the learning guides, `ARCHITECTURE.md` and
`SCIENTIFIC_VALIDATION.md`; this log only points to it. New entries are added after each
merge: the `simforge-status` skill drafts them from the learning handoff in
`docs/HANDOFF.md`, and an entry is added only once the author approves it, in the branch of
their next change (never directly on `main`).

**Commit hashes below were rewritten on 2026-11-02** (all commits now authored by Mud0709 with
Claude as co-author). The hashes in these entries are the old ones; `docs/history-rewrite-map.txt`
maps each to its new hash. GitHub PR pages keep the old hashes.

---

## Roadmap 2.2: angle sweeps for both drag laws
- **Merged:** PR #14, `0ea819a` (2026-10-29).
- **What it does:** the best launch angle with quadratic drag: a grid of 2.1 runs, the best
  grid angle refined by bounded Brent, and an accuracy estimate for that angle; a sweep panel
  on the quadratic-drag page (export, compare, reopen). The linear sweep is unchanged. Also
  adds the autopilot's daily allowance and push notifications.
- **Key concepts:** at a smooth maximum the curve is flat, so if the computed range is within
  ε_R of the true one, the best angle is within about 2√(ε_R/K) (to a quadratic
  approximation; a square root, so the angle is less certain than the range); validating against the vacuum answer (45°) and a weak-drag first-order result; a
  work budget (300 000 force evaluations) so a request finishes within the 30 s proxy limit.
- **Decisions and trade-offs:** a new model rather than an option on 2.1; the accuracy is
  labelled an estimate, not a bound; the best grid point is kept if it beats Brent's
  refinement.
- **Revisit:** why the angle accuracy scales with the square root of the range accuracy.
- **Next:** 2.3, simple, damped and driven oscillators.

## Roadmap 2.1: projectile motion with quadratic drag
- **Merged:** PR #13, `646e996` (2026-10-28).
- **What it does:** a new model and page for air resistance F = −c|v|v, with no exact 2-D
  solution, checked against the exact vertical rise (tan) and fall (tanh), terminal speed
  √(mg/c), the c → 0 limit, an energy balance and the hodograph invariant.
- **Key concepts:** validating without an exact answer; a wrong force law passes the 1-D
  references but fails energy and the invariant; the drag time S = ∫κ|v| dt as the solver's
  real cost; last-bit CPU differences need written tolerances.
- **Decisions and trade-offs:** a new model, not an option (keeps old runs replayable);
  the guard redesigned after measuring the planned one over-refuse 193 of 1007 runs;
  measured input rules (atol ≤ 1% of the slowest speed; flight ≥ 1 µs).
- **Revisit:** why exact step counts in replay can differ between CPUs.
- **Next:** 2.2, angle sweeps for both drag laws.

## Roadmap 1.6: comparison and export
- **Merged:** PR #12, `82ca0b2` (2026-10-25).
- **What it does:** pin a reference run and overlay a run of the same model, with a table
  of input and summary changes; recompute a stored run's series (digest-checked); export
  CSV in the browser and a versioned JSON record. Completes Phase 1.
- **Key concepts:** recompute, don't store (the digest proves a match); RFC 4180 and exact
  number round-trip; CSV formula injection (numbers exempt); relative change undefined at
  a zero reference; tolerances are not significance tests.
- **Decisions and trade-offs:** CSV made in the browser (covers unsaved runs and uploads);
  reference in the URL, not the database; same-model overlay only; a fresh reviewer per
  slice caught four bugs.
- **Revisit:** why "not bit-identical" no longer claims a cause.
- **Next:** Phase 2, starting with 2.1 quadratic drag.

## Roadmap 1.5: a usable experiment log; the autopilot
- **Merged:** PR #11, `d949170` (2026-10-24).
- **What it does:** the experiment log gets headlines written by each model, a lab filter and
  paging; a saved run reopens on its page with its inputs; Replay from the log shows the
  verdict; runs can have a name and a note (schema v3). Also adds the autopilot protocol,
  state and journal, and records the 1.6 plan (comparison and export).
- **Key concepts:** labels vs results (PATCH may change only the name and note); migrations
  that chain v1 → v2 → v3 in one transaction; a race condition in parallel e2e tests ("the
  newest row" was another test's run).
- **Decisions and trade-offs:** reopening fills the form but runs nothing; replays are saved
  only when asked; the autopilot never merges and pauses after 6 commits without the author.
- **Revisit:** why an uploaded file has to be supplied again to reopen or replay its run.
- **Next:** roadmap 1.6, run comparison and export.

## Roadmap 1.4: model registry, run record v2 and replay
- **Merged:** PR #10, `9ed5c21` (2026-10-23).
- **What it does:** one registry entry per model and one shared run path; run record v2 with
  an output digest, code identity and a backed-up migration of v1 logs; golden runs; replay
  with a verdict: identical, within tolerance or differs.
- **Key concepts:** a digest (SHA-256 of canonical JSON) shows bit-identity, not correctness;
  tolerances declared in advance, each with a reason; CI's CPUs changed the last bits
  (summation order), about 1e-15 relative.
- **Decisions and trade-offs:** golden runs pass on a matching digest, otherwise only within
  tolerance, with a warning saying so; each run records its CPU model; the original run is
  never changed, a replay is a new linked record.
- **Revisit:** why the same code and libraries gave different digests on another machine.
- **Next:** 1.5, a usable experiment log.

## Review fixes: Economy, Workspace UI and docs
- **Merged:** PR #9, `41ee90e` (2026-10-22).
- **What it does:** fixes the remaining review findings: the Solow convergence note's real
  reason, a fuller bit-identity check; a Workspace out-of-date note and status line, a
  Parameters panel never taller than the window; IB Foundations and roadmap wording.
- **Key concepts:** results marked out of date when the form no longer matches them; a
  worst-case uncertainty bound (IB rules) vs a typical spread (Monte Carlo).
- **Decisions and trade-offs:** the ROADMAP no longer says "verified" for what was not
  checked; a shared AssumptionsList replaces four copies.
- **Revisit:** why IB's uncertainty rules are exact for sums but only first order for
  products.
- **Next:** roadmap 1.4.

## Review fixes: Physics and Quant labs
- **Merged:** PR #8, `c80fd6d` (2026-10-21).
- **What it does:** fixes bugs found by reviewing all merged work: a false t = 0 landing,
  physical input limits, exact vertical launch, stray-quote rejection, private error
  messages, exact SD 0 for constant columns.
- **Key concepts:** an event at the starting point; limits on derived quantities (k = b/m);
  mutation checks prove a test can fail; middleware order decides which layer answers.
- **Decisions and trade-offs:** some previously accepted (absurd) inputs are now refused,
  each with a reason; near-vertical rounding left alone (it is rounding of the input).
- **Revisit:** why the t = 0 bug looked like *perfect* accuracy.
- **Next:** remaining Economy, Workspace UI and docs fixes; then 1.4.

## Claude Code project setup
- **Merged:** PR #7, `b041fc9` (2026-10-21).
- **What it does:** project skills (debugging, verification, TDD, grilling, status) and a
  cloud-session hook that installs dependencies.
- **Key concepts:** CLAUDE.md is the only memory that persists; a hook's stdout enters the
  context.
- **Next:** review fixes (PR #8).

## Roadmap 1.3: Quant Lab CSV import and dataset profile
- **Merged:** PR #6, `e8b3371` (2026-10-19).
- **What it does:** imports a CSV (or a bundled synthetic sample) and describes it: column
  types with reasons and overrides, missing values, exact duplicates, descriptive statistics,
  preview and charts. Descriptive only: nothing is inferred or predicted.
- **Key concepts:** parsing bytes → text → rows; strict type inference that flags ambiguity
  (`1,200`, `007`, `01/02/2024`, `NA` = Namibia); missing vs invalid; type-7 quartiles and
  sample SD (n − 1) vs IB's σ (n); overflow-safe statistics by power-of-two scaling; a hash
  identifies bytes, it does not prove the data are right.
- **Decisions and trade-offs:** no pandas yet (stdlib `csv` + NumPy, easier to control);
  datasets are request-only, never stored; base64 upload inside JSON so the strict schema
  applies; a request-size guard on every route.
- **Revisit:** why position-based overrides had to be cleared when the delimiter changes;
  why a one-column file cannot tell a blank line from an empty value.
- **Next:** roadmap 1.4, run record v2, model registry and replay.

## Roadmap 1.2: Physics pages in the shared workspace
- **Merged:** PR #5, `43bd4ce` (2026-10-16).
- **What it does:** the projectile and integrator pages use the same five-region workspace as
  the Solow page (Parameters, Visualisation, Results, Assumptions, Validation).
- **Key concepts:** UI refactor vs scientific engine (the numbers did not change, so the
  backend tests could not move); what "Validation" means on each page.
- **Decisions and trade-offs:** one component per region, reusing the Solow pattern rather
  than a new abstraction; Assumptions and Validation stacked full width because the error
  tables did not fit at half width.
- **Revisit:** which tests would catch a changed number, and which would not.
- **Next:** 1.3, the Quant Lab's first feature.

## IB Foundations track recorded (docs only)
- **Merged:** PR #4, `621f16c` (2026-10-16).
- **What it does:** records Track A, simpler IB-aligned simulations, as an additive track
  mapped to the official Physics (2025) and Economics (2024) guides.
- **Key concept:** additive means Track A never replaces, reorders or blocks Track B.
- **Revisit:** whether and when to interleave a Track A module (A2 is optional).

## Roadmap 1.1: Economy Lab, Solow growth model
- **Merged:** PR #3, `04e5c30` (2026-10-15).
- **What it does:** a discrete-time Solow model with a savings-policy experiment, in the
  first version of the shared workspace, with per-run checks.
- **Key concepts:** steady state and convergence; the golden rule (s = α); computing
  `n + g + ng + δ` and `1 − ρ` directly to avoid cancellation; proofs vs tests vs empirical
  bounds.
- **Revisit:** `docs/ECONOMY_LEARNING_GUIDE.md` exercises.

## Phase 0: Physics foundation, integrator study and angle sweep
- **Merged:** PR #1, `543b98e`, and PR #2, `0636ae9` (2026-10-15).
- **What it does:** projectile motion with linear drag solved exactly and numerically; a
  from-scratch convergence study of Euler, RK4 and Verlet; range against launch angle.
- **Key concepts:** exact vs numerical solutions; convergence order and log-log plots; a
  pre-declared fit rule; floating-point rounding and catastrophic cancellation.
- **Revisit:** `docs/LEARNING_GUIDE.md` checkpoints and exercises.
