# SimForge learning log

One short entry per merged milestone, newest first: what was built, what it taught, and what
to revisit. Detail lives in the learning guides, `ARCHITECTURE.md` and
`SCIENTIFIC_VALIDATION.md`; this log only points to it. New entries are added after each
merge: the `simforge-status` skill drafts them, and an entry is added only once the author
approves it, in the branch of their next change (never directly on `main`).

---

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
