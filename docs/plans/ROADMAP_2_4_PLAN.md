# Roadmap 2.4 plan: the methods workbench for any time-stepping model

Written on 2026-11-19 by the `planner` (self-grilled, D1-D17). Inputs taken in:
`docs/plans/ROADMAP_2_4_NOTES.md` (per-run checks for the three Phase 0 models, the duplicated
landing logic, the open table decision), ROADMAP row 2.4 and the capability map's
"Numerical methods workbench" row (Core: "the same workbench for any time-stepping model,
symplectic Euler and Verlet, long-run energy drift, event-location error"; Ext: Boris pusher).

## Grilling record (2026-11-19)
The author's instruction (2026-11-19, a human chat): "Continue with 2.4. In this tick, plan and
build all of it. Choose the recommended in grilling." So the planner grilled itself (rounds
below) and **every recommendation is adopted**; nothing was put to the author.
- **Who writes the symplectic methods.** The 2.3 plan's grilling record (D4) left them "in 2.4,
  where the author writes them". The new instruction supersedes it: **Claude builds all of 2.4
  this tick.** To keep the learning goal, the guide chapter (D16) walks the author through the
  symplectic Euler and velocity Verlet code line by line (`<!-- src: -->` excerpts) and ends
  with an exercise to write position Verlet himself and check its conserved quantity.
- **The notes' open decision** "keep the exact-vs-numerical table beside the new checks":
  recommended yes, taken yes (D5).

## Amendments during the build (2026-11-19)
- **Order-fit error (D8, D9; slice 2, under "take the recommended").** The oscillator fits
  e(h) = max over step nodes of √(Δq² + (Δv/ω)²)/X. Measured: symplectic Euler's error at
  t = T is order 2 for every start (it is conjugate to Verlet by an O(h) half-kick, which
  cancels when the exact flow returns to its start); the max over nodes gives 1.00 (symplectic
  Euler) and 2.00 (Verlet).

## Slice status
- Slices 1-5: not started.

## Scope
**In:** generic fixed-step tools in `numerics/` (two symplectic steppers, event location,
a convergence driver, energy-drift statistics); one new model, the undamped oscillator's
methods study (`physics.oscillator.integrators`, v1.0.0); the projectile study moved onto the
same driver, with the **landing-time (event-location) error** added; per-run `checks` for the
three Phase 0 models (v1.1.0 each); the duplicated adaptive landing logic shared.
**Out** (Track B order unchanged, Track A untouched): generic sweeps (2.5), animation (2.6),
the Boris pusher (Ext), orbits (Phase 2 capability map "Orbits", later), damped/driven or
quadratic-drag fixed-step studies (Not done, below).

## Before deciding
1. **What a professional would do that a naive plan would not.** (a) Separate the two
   questions: *order* is measured over a short horizon (one period), *long-time behaviour*
   (energy drift) over many periods at one practical step; on a long horizon symplectic
   Euler's O(h²)·t phase error swamps its O(h) shape error and the fitted order means
   nothing. (b) Judge symplectic methods by their **modified (shadow) energy**, which is
   conserved exactly by the discrete map, not by "the energy looks flat". (c) Place the event
   **mid-step** (h = T/(N + ½)) when measuring event-location error: with h = T/N the exact
   event sits on a node and the interpolation error vanishes by construction. (d) Separate
   the integrator's error from the interpolant's: RK4 with a linear interpolant is only
   second order at the event. (e) Downsample an oscillating energy series by a min/max
   envelope, never by picking points, so a bounded oscillation cannot alias into a "drift".
2. **Raw material.** `numerics/fixed_step.py` (Euler, RK4, `integrate_fixed`,
   `DIVERGENCE_THRESHOLD`, stability functions), `numerics/convergence.py` (`fit_order`,
   `local_orders`), `physics/projectile/integrator_study.py` (fit rule, round-off floor
   `100·N·ε·scale`, implicit-drag Verlet, linear invariant), `physics/projectile/analytical.py`
   (`flight_time`, validated), `physics/oscillator/analytical.py` (validated to 1e-13 against
   90 digits), the two `integrate()` functions in `numerical.py:58-127` and
   `quadratic_numerical.py:81-153` (identical event logic), `ChecksTable`.
3. **Methods and tools.** NumPy, SciPy (`brentq` for the Hermite root), stdlib `fractions`
   (exact rational iteration of the step maps) and `decimal` (50 digits for long runs).
   **mpmath is not a dependency** (checked: `backend/pyproject.toml`; `import mpmath` fails in
   the backend environment), so no new dependency is added.
4. **What proves it right, other than Claude saying so.** The closed forms R1-R8 below,
   checked in exact rational arithmetic (they were: scratch run 2026-11-19, `fractions`, 30
   steps for each invariant, 19 and 14 steps for the Euler and RK4 factors, all equal
   exactly); the exact vacuum landing time and the validated linear-drag flight time;
   interpolation-error leading terms (measured in scratch: orders 1.99996 and 4.00001 on
   e^t − 2); the proved energy bounds R5 (300 random float cases in scratch reached 0.99998 of
   the bound, never above: tight, so the check needs a rounding allowance); the golden digests
   of untouched models staying bit-identical through the two refactors.

## Design tree and rounds (self-grilled)
- **Round 1** (no prerequisites): D1 what "the workbench" is; D2 which models use it; D3 who
  writes the steppers; D4 which methods; D5 the Phase 0 checks and the table; D6 references
  and dependencies.
- **Round 2** (needs D1-D4): D7 code layout; D8 oscillator study inputs and limits; D9 fit
  rule; D10 energy drift; D11 event location; D12 the landing dedup.
- **Round 3** (needs round 2): D13 per-run checks; D14 response, versions, golden runs;
  D15 frontend; D16 docs and guide; D17 seams.

Each decision: options, **choice** (the recommendation, adopted), reason. Reversal: before the
slice that owns it, edit the decision; after, edit that slice.

## Decisions
- **D1. What "the workbench for any time-stepping model" is.** (a) one page where the user
  picks any model; (b) **a pure, model-free driver in `numerics/workbench.py` plus one study
  per model**, each with its own endpoint and page; (c) an oscillator-only study. (a) needs a
  plugin registry and generic forms (a speculative framework); (c) leaves the projectile on
  its own copy, so it is not "the same workbench". (b) follows ARCHITECTURE decision 9 (generic
  numerics apart from models): a model supplies a `Problem` (rhs, initial state, exact states,
  scales, its fit-rule exclusion function); the driver runs methods × steps, measures errors
  and fits orders. This is a numerical method in `numerics/`, not a cross-lab abstraction, and
  two real models use it within this step.
- **D2. Which models.** **The projectile (existing study, plus event location) and the
  undamped, undriven oscillator (new: symplectic methods, energy drift).** Options not taken:
  damped/driven oscillator (not Hamiltonian, so the symplectic claims do not apply);
  quadratic drag (no exact 2-D reference for fixed-step errors). Both go to Not done.
- **D3. Who writes the steppers.** **Claude** (Grilling record). The guide walks the code.
- **D4. Methods.** **Oscillator: Euler, RK4, symplectic Euler (kick then drift), velocity
  Verlet. Projectile: unchanged (Euler, RK4, implicit-drag Verlet).** Not taken: position
  Verlet (the guide's exercise), the drift-then-kick Euler variant (one variant suffices; its
  invariant is recorded in R3), Yoshida/higher-order symplectic, implicit midpoint (implicit
  solves), Boris (Ext). The symplectic steppers take an acceleration `a(t, q)` that must not
  depend on velocity; that is stated in their docstrings and the projectile's implicit-drag
  Verlet stays where decision 9 put it.
- **D5. Phase 0 checks** (notes §1). **Done in this step, one bump per model to 1.1.0, and the
  exact-vs-numerical tables stay beside the checks** (the table shows the numbers; the checks
  give the verdict). Not taken: a separate step (two bumps for the same models).
- **D6. References and dependencies.** **`fractions` and `decimal`, no new dependency.** The
  test references are R1-R8 (closed forms), exact rational iteration, 50-digit `decimal`, the
  vacuum landing time and `analytical.flight_time`; never the code's own output.
- **D7. Code layout.**
  `numerics/fixed_step.py`: `symplectic_euler(accel)` and `velocity_verlet(accel)` stepper
  factories for y = (q, v); harmonic test-equation closed forms beside the existing stability
  functions (`harmonic_energy_factor`, `modified_energy`, `harmonic_phase_per_step`,
  stability limits). `numerics/events.py`: `first_crossing` (first downward sign change of a
  component over nodes) and `locate_crossing(..., kind="linear" | "hermite")`.
  `numerics/workbench.py`: `Problem`, the convergence driver (moved, generalised, from
  `integrator_study._run`), `energy_envelope` (min/max per bin) and energy statistics.
  `physics/oscillator/integrator_study.py`, `integrator_schemas.py`, `integrator_model.py`; the
  endpoint `POST /api/v1/physics/oscillator/integrators` in `api/routes/oscillator.py`.
  `physics/projectile/landing.py`: the shared adaptive solve to landing (D12).
- **D8. Oscillator study inputs (SI) and limits.** `mass` kg, `spring_constant` N/m,
  `initial_displacement` m, `initial_velocity` m/s (the oscillator's field types and bounds);
  `dt_values` s (2-12, distinct; order study over **one period**, max error over its nodes, D9); `methods` (1-4, distinct);
  `energy_dt` s and `periods` (1-1000) for the long run. **Defaults:** m = 1, k = 25
  (ω = 5 rad/s, period ≈ 1.257 s), x₀ = 0.1, v₀ = 0, `dt_values` = 0.04/2ⁱ, i = 0..7
  (ωh = 0.2 → 0.0016), `energy_dt` = 0.05 (ωh = 0.25), `periods` = 200. Refused (422, naming
  the number): x₀ = v₀ = 0 (no energy to measure); per-run and total step caps, starting from
  the projectile study's 50 000 / 150 000 and **set from measured worst-case time** in slice 2
  (≤ 5 s on the dev machine, recorded in `SCIENTIFIC_VALIDATION.md`).
- **D9. Fit rule (stated before results).** Oscillator, per run: excluded if diverged; if
  ωh > 0.2 (not asymptotic); if the closed-form amplitude growth over the period exceeds 10%,
  |ρᴺ − 1| > 0.1 with ρ from R1/R2 (a priori; it only bites Euler, θ ≳ 0.03); if the error is
  below the floor 100·N·ε·X (X = √(x₀² + (v₀/ω)²)). **Fitted error** (amended 2026-11-19):
  e(h) = max over the period's step nodes of √(Δq² + (Δv/ω)²)/X, never the error at t = T
  alone (symplectic Euler's end-of-period error is order 2: see Amendments). Stability (R7) is reported, not used: Euler is
  unstable at every h on the oscillator yet converges at a fixed horizon. Projectile: rule
  unchanged (`integrator_study.py:74-81`).
- **D10. Energy drift.** One run per method at `energy_dt` over `periods`. Reported: the
  relative energy error (E_n − E₀)/E₀ as a min/max envelope in ≤ 200 bins; its max and final
  values; the closed-form prediction (R1, R2 factors; R5 bounds); for symplectic methods the
  modified-energy residual max|H̃_n − H̃₀|/H̃₀ (R3, R4). Labels: Euler grows (exact factor),
  RK4 decays (exact factor), symplectic bounded (proved) with no secular drift.
- **D11. Event location** (projectile study). For each run with N steps, a second fixed-step
  run with **h_e = T/(N + ½)** over the first downward crossing of y = 0 (cap 2N + 2 steps;
  no crossing: excluded with a reason). The landing time is located by **linear**
  interpolation and by **cubic Hermite** (values y and slopes v_y at both nodes; root by
  `brentq` on the bracket, `xtol` ≤ 1e-15·T, well below the smallest measurable error).
  Reference: `analytical.flight_time` (independent, validated). Predicted orders
  min(p, 2) and min(p, 4) (R6): Euler 1/1, RK4 2/4, Verlet 2/2. Event runs count toward
  a reported cost but **the step caps are unchanged** (a new cap would refuse stored runs on
  replay); worst-case time measured in slice 4.
- **D12. Landing dedup.** **`physics/projectile/landing.py`**, used by `numerical.integrate`
  and `quadratic_numerical.integrate` (the ground event with its t > 0 guard, the apex event,
  status handling); projectile-local, because both users are projectile models and the event
  is "y = 0 while descending". Must be **bit-identical**: proved by the golden digests of the
  quadratic model and its sweep (no version change) and of v1.0.0 projectile before its bump.
- **D13. Per-run checks** (`ValidationCheck`, decision 12; above 100% gives `passed = null`).
  *Oscillator study:* per method with a fit, order within 0.1 of theory (diagnostic); per
  method, the long run's E_N/E₀ against R1/R2 (Euler, RK4) or max H̃ residual (symplectic)
  within C·N·ε (exact identity; C measured, 1-2-5, ≥ 10× the worst). **Euler's row compares
  E_N/E₀ with (1 + θ²)^N while the run stays finite, whatever its stability** (the identity
  holds for every θ). Symplectic max |ΔE|/E₀ within **R5 bound + C·N·ε** (additive: rounding
  adds about N·ε regardless of θ; C measured as for the H̃ row; label **proved bound**, not
  exact identity). A run that diverges (`DIVERGENCE_THRESHOLD`, `fixed_step.py:39`) reports
  status "diverged" with the step at which it did, and its energy rows give `passed = null`
  with that reason; symplectic runs at θ ≥ 2 (R7) give no verdict on the R5 row. Fit counts
  and excluded runs (info).
  *Projectile study:* the notes' rows (order within 0.1; δv = −k·δr for Euler and RK4 to
  measured rounding; counts) plus landing-time order within 0.1 of R6 per method and
  interpolant. *Projectile:* flight time, range, max height against the exact solution and the
  energy balance, thresholds `F·(rtol + atol/scale) + floor` measured on a grid (form of 2.1).
  *Linear angle sweep:* interior peaks on the grid = 1 (diagnostic); **range with drag ≤
  vacuum range at every angle and for the best angle** (**proved inequality**, R8, with an
  allowance c·ε·range measured).
- **D14. Response, versions, golden runs.** New fields only; nothing renamed.
  `physics.oscillator.integrators` v1.0.0 (hash: parameters, dt_values, methods, energy_dt,
  periods; summary: fitted orders, final energy errors; one replay tolerance rule per stored
  field), golden case **appended**. `physics.projectile`, `.integrators`, `.angle_sweep` →
  **1.1.0**, their three golden entries **re-pinned**; every other digest unchanged. Stored
  v1.0.0 runs of those three stay readable; replay and recompute refuse them with the existing
  409 message (`api/rerun.py:67-71`), as for quadratic v1.0.1. `make api-types` regenerates
  `openapi.json` and `schema.d.ts`.
- **D15. Frontend.** New page `/physics/oscillator/integrators` in `Workspace` (orders chart,
  energy-drift chart with one line per method and the envelope band, a modified-energy
  table, `ChecksTable`), linked from `/physics/oscillator`; the integrators page gains a
  landing-time table and chart and `ChecksTable`; the projectile and linear-sweep pages gain
  `ChecksTable`, tables kept. 1.6 wiring for the new model: response union, headline,
  `exportTables`, `compare`, `overlay`, a `stored-fields` case. Reusing the existing order
  chart is the builder's choice.
- **D16. Docs.** Each backend slice writes its `SCIENTIFIC_VALIDATION.md` section (measured
  numbers, machine). Close-out: ARCHITECTURE decision 21 (the workbench) and updates to
  decisions 9 and 12 and the endpoint table; README; ROADMAP 2.4 ✅ with this plan's path and
  the capability-map row; `docs/LEARNING_GUIDE.md` **Part 21** (≈ 250 lines: intuition, the
  shadow energy on the SHO, event location; line-by-line `src`-tagged walk-through of the two
  symplectic steppers; checkpoints; exercises without solutions, including "write position
  Verlet (drift, kick, drift) and find and test its conserved quantity"); brief
  `docs/briefs/2.4.md`.
- **D17. Seams** are below; they are the confirmed seams for `tdd`.

## Reference formulas (derived for this plan)
Harmonic test equation q̈ = −ω²q, u = v/ω, θ = ωh, E ∝ q² + u² (E = ½kq² + ½mv²).
- **R1 Euler.** (q, u) ↦ (q + θu, u − θq), so E_{n+1} = (1 + θ²)E_n exactly; ρ = √(1 + θ²),
  unstable for every θ > 0.
- **R2 RK4.** z = q + iu obeys ż = −iωz, so z_{n+1} = R(−iθ)z_n and
  E_{n+1}/E_n = |R(iθ)|² = 1 − θ⁶/72 + θ⁸/576 (expanded by hand); decays for θ < 2√2.
- **R3 Symplectic Euler (kick, drift):** v ← v − hω²q, q ← q + hv. Conserved exactly:
  H̃ = q² + v²/ω² − h·q·v (derived by solving MᵀQM = Q for Q = [[1, a], [a, 1]] in (q, u):
  a = −θ/2). The drift-then-kick variant conserves q² + v²/ω² + h·q·v.
- **R4 Velocity Verlet:** H̃ = (1 − θ²/4)q² + v²/ω². In (q, u) the step is
  M = [[c, θ], [−θβ, c]], c = 1 − θ²/2, β = 1 − θ²/4; then βq′² + u′² = βq²(c² + θ²β) +
  u²(c² + θ²β), the cross terms cancel, and c² + θ²β = 1.
- **R5 Proved energy bounds** (θ < 2). From R3, |qu| ≤ E/2:
  |E_n − E₀|/E₀ ≤ θ/(1 − θ/2) (symplectic Euler). From R4, E_n = H̃ + (θ²/4)q_n² and
  q_n² ≤ H̃/β: |E_n − E₀|/E₀ ≤ (θ²/4)/(1 − θ²/4) (Verlet). Bounded for all n: no secular drift.
  A proved bound in exact arithmetic; the float check adds C·N·ε (D13).
- **R6 Event location.** With a crossing at fraction s of a step and g the event function,
  linear interpolation errs by s(1 − s)h²g″/(2|g′|) + O(h³); cubic Hermite by
  s²(1 − s)²h⁴g⁗/(24|g′|) + O(h⁵) (at s = ½: h²g″/(8|g′|) and h⁴g⁗/(384|g′|)). Hermite is
  exact for cubics. Adding a method of order p, the landing-time error is O(h^min(p, q)),
  q = 2 (linear) or 4 (Hermite).
- **R7 Stability and phase on the test equation.** Symplectic Euler and Verlet: trace
  2 − θ², stable for θ < 2, phase per step φ = arccos(1 − θ²/2) = θ + θ³/24 + …; RK4 stable
  for θ ≤ 2√2; Euler unstable for θ > 0.
- **R8 Drag never lengthens the range** (a proved inequality; linear drag, vₓ₀ > 0, any launch height). With
  u = kx/vₓ₀: y_drag(x) = h₀ + x tan α + (g/k²)(u + ln(1 − u)) and
  y_vac(x) = h₀ + x tan α − (g/k²)u²/2; since u + ln(1 − u) = −u²/2 − u³/3 − … ≤ −u²/2, the
  drag path is never above the vacuum path at the same x, so it lands no farther.

**Status:** R1-R4 checked exactly in rational arithmetic (scratch, 2026-11-19, not a repository
test); R5 checked on 300 random float cases (ratio ≤ 0.99998); R6 orders checked on e^t − 2 at
s = ½ (local orders 1.99996-1.99999 and 4.00001-4.0029; errors equal h²/8 and h⁴/384 to 3
digits). R7 and R8 derived on paper only; slices 1 and 3 test them.

## Seams (where tests attach; what each catches and misses)
1. **Steppers and closed forms** (`fixed_step.py`): R1-R5, R7 against `fractions`/`decimal`
   iterations and float runs. *Catches* stepper and formula errors. *Misses* the driver.
2. **Event location** (`events.py`): R6 on functions with known roots (e^t − 2, the vacuum
   parabola from exact nodes, a cubic). *Catches* interpolant and bracketing errors.
3. **Driver** (`workbench.py`): a synthetic `Problem` with a known error law; the projectile
   study's v1.0.0 numbers bit-identical after the move. *Catches* bookkeeping and fit errors.
4. **Model runs and checks** (both studies, projectile, sweep): checks pass on corner grids; a
   planted error fails one; nulls where no verdict. *Catches* assembly and threshold errors.
5. **API and registry**: 422s, golden digests (re-pinned three, appended one, rest unchanged),
   replay, contract. 6. **Frontend**: Vitest and Playwright; *misses* science (seams 1-4).

## Slices (test-first with `tdd`: `test-writer-risky` then `builder-risky`, then a fresh `reviewer`)
Common commands (from `backend/`): `uv run ruff check . && uv run ruff format --check .`,
`uv run mypy`. "No existing test changed" means
`git diff --stat --diff-filter=MDR HEAD -- backend/tests` lists only the files the slice names.

### Slice 1: numerics core (risky: numerics, references, tolerances)
Symplectic Euler and velocity Verlet steppers, harmonic closed forms, `events.py`,
`workbench.py` (driver and energy envelope; not yet used by any model). SV: a short
"numerics/" subsection under the integrators section.
**Acceptance.**
- **Test files (new):** `backend/tests/numerics/test_symplectic.py`,
  `backend/tests/numerics/test_events.py`, `backend/tests/numerics/test_workbench.py`.
- **Commands:** `uv run pytest tests/numerics -q` (red before, green after);
  `scripts/run_logged.sh s1-pytest 'cd backend && uv run pytest -q'`; the common commands;
  the `git diff` above (prints nothing).
- **Checks:** (1) In `fractions`, H̃ (R3, R4) is exactly constant over ≥ 30 steps and E
  follows R1, R2 exactly; the float steppers keep H̃ within C·n·ε over 10⁵ steps, C justified
  in a comment? (2) The float energy bounds R5 hold on a random grid (θ ∈ (0, 1.9)) with the
  stated rounding allowance, and Verlet at θ = 2.01 is flagged unstable? (3) Linear and
  Hermite crossings on e^t − 2 at s = ½ give fitted orders 2 ± 0.02 and 4 ± 0.02 and match
  R6's leading terms within 1% at the finest h; Hermite is exact (≤ 8ε relative) on a cubic?
  (4) The driver, on a synthetic problem with error C·h^p, recovers p and applies a supplied
  exclusion rule; the envelope keeps each bin's min and max? (5) Full `pytest -q`, ruff,
  format and mypy pass and no existing test file changed?

### Slice 2: the oscillator methods study and its API (risky: scientific core, limits)
`physics/oscillator/integrator_{study,schemas,model}.py`, the route, `ModelEntry`, registry,
response union, golden case appended to `tests/api/test_registry.py`, `make api-types`, SV
section `physics.oscillator.integrators` v1.0.0 with measured C, caps and timings.
**Acceptance.**
- **Test files:** new `backend/tests/physics/test_oscillator_integrators.py` (orders, energy
  checks, a corner grid, a planted mutant: Verlet's second half-kick using the old position,
  which must fail the H̃ check), new `backend/tests/api/test_oscillator_integrators_api.py`
  (422s: NaN, ±Infinity, x₀ = v₀ = 0, duplicates, each step cap naming N); appended case in
  `backend/tests/api/test_registry.py`; `backend/tests/api/golden_runs.json`.
- **Commands:** `uv run pytest tests/physics/test_oscillator_integrators.py
  tests/api/test_oscillator_integrators_api.py -q`; `uv run pytest tests/api/test_registry.py
  tests/api/test_golden_digests.py -q`; `scripts/run_logged.sh s2-pytest 'cd backend && uv
  run pytest -q'`; from the root `make api-types` then `git diff --stat frontend/src/lib/api`.
- **Checks:** (1) On the default request and a corner grid (ω at its bounds, x₀ only, v₀ only,
  both; `periods` 1 and 1000 within the caps), every check of a finite run passes, Euler's
  energy row matches (1 + θ²)^N while finite, a run that reaches `DIVERGENCE_THRESHOLD`
  (e.g. Euler at the defaults with `periods` = 1000) reports "diverged" with its step and
  `passed = null` on its energy rows, and the four fitted orders are within 0.1 of 1, 4, 1, 2?
  (2) The mutant fails the modified-energy check while the true
  code passes? (3) Each refusal is a 422 naming its number, and the caps and C are named
  constants whose comments cite the measurement recorded in SV? (4) Golden digests of all
  existing models are unchanged and the new case is appended (not inserted)? (5) Full pytest,
  ruff, format, mypy pass and the regenerated contract is committed with the slice?

### Slice 3: projectile and linear-sweep checks; shared landing logic (risky: thresholds, refactor of two solvers)
Order inside the slice: (a) `landing.py` and both solvers through it, **golden digests run
before any version bump**; (b) checks for `physics.projectile` and `.angle_sweep`, both to
1.1.0, re-pin, `make api-types`, SV updated (thresholds with grid and machine; the
"duplicated event logic" limitation removed).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/test_landing.py` (both solvers via the helper;
  horizontal launch apex; the t = 0 guard), `backend/tests/physics/test_projectile_checks.py`
  (default passes; threshold grid RK45/DOP853/Radau × tolerance pairs × corners; wrong drag
  sign fails; R8 per angle including cliff launches; `passed = null` above 100%);
  `backend/tests/api/golden_runs.json` re-pinned.
- **Commands:** after (a): `uv run pytest tests/api/test_golden_digests.py -q` (all pass,
  v1.0.0 unchanged); after (b): `uv run pytest tests/physics/test_landing.py
  tests/physics/test_projectile_checks.py -q`; `uv run python -m tests.api.pin_golden_runs`
  then `git diff backend/tests/api/golden_runs.json`; `scripts/run_logged.sh s3-pytest 'cd
  backend && uv run pytest -q'`; `make api-types`.
- **Checks:** (1) After (a), every golden digest is unchanged (the dedup is bit-identical)?
  (2) The default runs of both models show their checks, all passing, and the wrong drag sign
  fails at least one? (3) The golden diff changes only the `physics.projectile` and
  `physics.projectile.angle_sweep` entries, both at 1.1.0? (4) Every threshold is a named
  constant citing its measurement in SV, and the existing projectile, sweep and quadratic test
  files are unchanged and pass?

### Slice 4: the projectile study on the workbench, with event location (risky: numerics, tolerances)
Order inside the slice: (a) `integrator_study.py` moved onto `numerics/workbench.py`, with no
other change, and **the golden digests run before any version bump** (the integrators'
v1.0.0 digest must be unchanged); only then (b) event runs (D11), checks (D13), schemas,
1.1.0, re-pin, `make api-types`; SV: "Fixed horizon, not landing" limitation replaced by the
measured event-location results.
**Acceptance.**
- **Test files:** new `backend/tests/physics/test_projectile_event_location.py` (orders per
  method and interpolant against R6 using `analytical.flight_time`; mid-step placement;
  no-crossing exclusion; δv = −k·δr check; a planted wrong interpolant slope fails);
  `golden_runs.json` re-pinned. Unchanged and passing: `test_projectile_integrators.py`,
  `tests/api/test_integrators_api.py`.
- **Commands:** after (a): `uv run pytest tests/api/test_golden_digests.py
  tests/physics/test_projectile_integrators.py tests/api/test_integrators_api.py -q` (all
  pass, v1.0.0 unchanged); after (b): `uv run pytest tests/physics/test_projectile_event_location.py
  tests/physics/test_projectile_integrators.py tests/api/test_integrators_api.py -q`;
  `uv run python -m tests.api.pin_golden_runs`; `scripts/run_logged.sh s4-pytest 'cd backend
  && uv run pytest -q'`; `make api-types`.
- **Checks:** (1) After (a), before any event code or bump, every golden digest is unchanged,
  the integrators' v1.0.0 included (the move onto the driver is bit-identical)? (2) On the default request the landing-time orders are within
  0.1 of 1/1, 2/4, 2/2 (linear/Hermite) and every check passes? (3) The worst-case request at
  the step caps runs within the measured time recorded in SV? (4) The golden diff changes
  only the integrators entry (1.1.0), and full pytest, ruff, format and mypy pass?

### Slice 5: frontend, guide, brief and close-out (routine)
D15 and D16; `docs/HANDOFF.md`; this plan's status.
**Acceptance.**
- **Test files:** new `frontend/src/components/OscillatorIntegratorLab.test.tsx`, new
  `frontend/e2e/oscillator-integrators.spec.ts`; updated `ProjectileLab.test.tsx`,
  `IntegratorLab.test.tsx`, `AngleSweepPanel.test.tsx`, `frontend/e2e/stored-fields.spec.ts`.
- **Commands:** from `frontend/`: `npx vitest run src/components/OscillatorIntegratorLab.test.tsx
  src/components/ProjectileLab.test.tsx src/components/IntegratorLab.test.tsx
  src/components/AngleSweepPanel.test.tsx`; from the root: `python3 scripts/check_excerpts.py`,
  `python3 scripts/doc_index.py --check`, `scripts/run_logged.sh e2e 'scripts/check.sh --e2e'`.
- **Checks:** (1) `scripts/check.sh --e2e` passes in full? (2) The new page runs its default,
  shows both charts and its checks, and a run saves, reopens and appears in the stored-fields
  case; the three projectile pages show `ChecksTable` and keep their tables? (3) Part 21's
  excerpts match the code (`check_excerpts.py` passes) and include the two symplectic
  steppers line by line, with exercises without solutions? (4) ROADMAP 2.4 is ✅ with this
  plan's path, ARCHITECTURE decision 21 exists, README lists the endpoint, and
  `docs/briefs/2.4.md` labels every claim proved, tested or observed?

## Risks
- **Fitted orders on user grids.** A coarse grid can miss the asymptotic regime and fail the
  "within 0.1" check; that is a true verdict about the grid, worded so in the check's note.
- **Tight bounds.** R5 is reached to 0.99998 in floats, so its check needs the rounding
  allowance; without it, honest runs fail.
- **Refactors not bit-identical** (D12, slice 4): reordered sums change digests; the golden
  run before each bump is the guard, and a mismatch is fixed, not re-pinned.
- **Cost.** Event runs roughly double a study's steps under unchanged caps; Python loops
  (≈ 17 µs per RK4 step) set the oscillator caps; both measured.
- **Replay of stored v1.0.0 runs** of the three Phase 0 models is refused (409) after the
  bump, as planned in the notes; no stored run is changed.
- **Unverified:** R7 and R8 numerically; all thresholds, caps and C (measured in slices).

## Out of scope / Not done
- Fixed-step studies of the damped or driven oscillator and of quadratic drag; phase-error
  reporting; position Verlet and the other symplectic Euler variant in code (the guide's
  exercise); higher-order symplectic methods; adaptive-solver event error analysis.
- Boris pusher (Ext), orbits and long-run Kepler comparison (capability map, later), generic
  sweeps (2.5), animation (2.6). The 25 lines of grid-and-Brent logic stay with 2.5.
- Review items (2026-11-19, worth doing, not applied): run `cd frontend && npx tsc --noEmit`
  after each `make api-types` (slices 2-4).
- A grep that every named threshold constant appears in the code and in SV.
- The sweep's "interior peaks = 1" check tested in `test_projectile_checks.py`.
- Split slice 5 into a frontend slice and a docs slice.
- Record damped/driven and quadratic-drag fixed-step studies as an open decision in HANDOFF; word the ✅ "a generic driver used by two models".
- A round-off floor (e.g. 100·N·ε·scale) for landing-time and oscillator errors, so near-exact RK4/Verlet + Hermite fits do not falsely fail.
- RK4 + Hermite O(h⁴) cancellation risk: test the coefficient, or give no verdict.
- Compare old and new `integrate()` outputs over a grid of inputs before deleting old code (one golden case per model is thin).
- Label O(h^min(p, q)) in R6 "standard result, tested in slice 4".
- Use a well-conditioned cubic for the ≤ 8ε Hermite test.
- Capability-map items with no Phase 2 step ("best angle against drag strength", "drag-law
  comparison") stay an open decision in `docs/HANDOFF.md`, untouched here.

## Genuine stops found
None. Checked: no new dependency (`backend/pyproject.toml` has numpy and scipy; mpmath is
absent and not added); no roadmap scope or order change (every item maps to the 2.4 row and
the capability-map Core list; Ext and later items stay out); Track A untouched; no new
storage of user data, network access or auth; stored runs are not modified (the bumps follow
the quadratic v1.0.1 precedent and the notes); no guard-rail file touched; every scientific
claim has an independent reference (R1-R8, `analytical.flight_time`, the vacuum landing time).
**Flagged, not blocking:** the 2.3 plan's "the author writes the symplectic methods" is
superseded by the author's 2026-11-19 instruction (Grilling record).
