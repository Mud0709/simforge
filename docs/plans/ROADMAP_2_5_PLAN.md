# Roadmap 2.5 plan: Generic sweeps

Status: **plan, not yet reviewed** (2026-11-22). It touches the scientific core (a new model,
its references and tolerances, a refactor of two validated sweeps), so it gets 3 `reviewer`s
in a planning-only tick (`CLAUDE.md`, "Reviews"; angles a, b, c of the autopilot skill step 3).

## Scope
**Row:** `ROADMAP.md:105`, "2.5 Generic sweeps." Phase 2 text (`ROADMAP.md:93-97`): "...
angle sweeps for both drag laws; ...; generic sweeps; animation." Earlier plans already
assigned two things to this step: the shared grid-and-Brent layer
(`docs/plans/ROADMAP_2_2_PLAN.md` D9; `ARCHITECTURE.md:435-437`: shared "until generic sweeps
(roadmap 2.5) give a shared layer more than two users") and the **simulated resonance curve**,
one run per drive frequency (`docs/plans/ROADMAP_2_3_PLAN.md` D9 and "Out of scope",
lines 194-199 and 574-575).

**In:** a model-free sweep driver in `numerics/sweep.py`; the linear and quadratic angle
sweeps moved onto it bit-identically; one new model, `physics.oscillator.resonance_sweep`
v1.0.0 (the simulated resonance curve, every point a 2.3 run, against the exact A(ω), δ(ω));
its API, page panel, checks, docs and guide chapter.
**Out** (Track B order unchanged; Track A and `backend/physics/foundations/` untouched): see
"Out of scope / Not done".

## Before deciding
1. **What a computational physicist would do that a naive plan would not.**
   (a) Read the steady-state amplitude by **demodulating at the drive frequency over whole
   drive periods** (a lock-in: project x(t) on cos ωt and sin ωt), not as max|x| of a sampled
   trace: the maximum is biased by where the samples fall and by the leftover transient, and
   gives no phase. On M ≥ 3 equally spaced samples per period, discrete orthogonality makes the
   projection of a pure sinusoid exact (R3 below), so the extraction adds no method error.
   (b) **Wait out the transient by a computed time**, from its exact decay rate γ and envelope
   R e^{−γt} (2.3's `analytical.transient_envelope`), the way an experimenter waits "several
   time constants", and carry what is left into the error budget as a proved term.
   (c) **Separate the error sources**: apply the same extraction to the exact x(t) at the same
   sample times (extraction plus transient only), and bound the numerical part by the run's
   measured trajectory error, so a mismatch with A(ω) can be attributed.
   (d) **Check with an invariant that does not use the closed form**: in steady state the mean
   drive power equals the mean damping power, ½F₀ωA sin δ = ½bω²A², so sin δ = bωA/F₀ (R4).
   (e) **Resolve the peak**: its width is about 2γ, so a grid with spacing Δω > γ flattens or
   misses it; report Δω/γ and refine the peak by a bounded search, with the accuracy estimate
   of 2.2 (u = 2√(ε/K)) labelled as an estimate.
   (f) **Refactor before adding**: move the two existing sweeps onto the driver with golden
   digests unchanged and no version bump, before the new model uses it; cap the sweep's cost
   in right-hand-side evaluations (reproducible), not seconds.
2. **Raw material (checked in the files).**
   `physics/projectile/angle_sweep.py:109-136` (grid, Brent on the neighbouring interval,
   grid point kept if it wins), `physics/projectile/quadratic_angle_sweep.py:199-307`
   (`_uncertainty`, budget counter inside `solve`, `interior_peaks`) and `:332` (`_aggregate`,
   per-check-id aggregation over runs); `physics/oscillator/analytical.py:277-352`
   (`SteadyState`, `steady_state`, `resonance_curve`, closed forms validated against a 90-digit
   reference: `SCIENTIFIC_VALIDATION.md:1116-1339`) and `:625` (`transient_envelope`, a proved
   bound |x − x_p| ≤ R e^{−γt}); `physics/oscillator/model.py:588-686` (`run`, its checks and
   `MAX_RUN_RHS_EVALUATIONS = 400_000`, `MAX_CYCLES = 500`), `numerical.py:66-99`
   (`OscillatorSolution` with SciPy dense output and `sample`); the frontend
   `AngleSweepPanel.tsx` (`SweepPanel`, `SweepAdapter`) and `QuadraticAngleSweepPanel.tsx`.
3. **Methods and tools.** NumPy; SciPy `minimize_scalar(method="bounded")` (in use) and
   `solve_ivp` dense output (in use); stdlib `fractions`/`decimal` in tests. No new dependency
   (`backend/pyproject.toml:12-13` lists numpy and scipy).
4. **What proves it right, other than Claude saying so.** The closed forms A(ω), δ(ω), ω_r,
   A_max, A(ω → 0) = F₀/k and A ~ F₀/(mω²) (R1, R2; validated in 2.3 against 90 digits); the
   exact discrete-orthogonality identity R3 checked on synthetic sinusoids in `fractions`-exact
   sample sums where possible and in floats to a stated ε allowance; the proved transient bound
   R5 checked on synthetic decaying signals; the power-balance invariant R4, which is
   independent of the closed form; planted mutants (a 1/T instead of 2/T lock-in factor; a
   sign error in the sine projection) that the checks must fail; for the refactor, the golden
   digests of `physics.projectile.angle_sweep` and `physics.projectile.quadratic_angle_sweep`
   unchanged and every existing sweep test passing.

## Decisions
Each: options, **choice**, reason. Reversal: before the owning slice, edit the decision;
after it, edit that slice.

- **D1. What "generic" means.** (a) one endpoint that sweeps any numeric input of any
  registered model (all three labs); (b) **a model-free driver in `numerics/sweep.py` (grid
  evaluation, bounded refinement of a maximum, interior-peak count, curvature estimate, work
  budget) used by three models, each with its own swept variable, schema and checks**; (c)
  leave the duplicated code and only add the resonance sweep. (a) is a registry-level,
  cross-lab framework: every swept input needs its own reference and refinement meaning, and
  the second lab that needs parameter sweeps is the Economy Lab in Phase 3 ("Sensitivity and
  uncertainty", `ROADMAP.md:49`); building it now would be speculative and would pull a
  Phase 3 item forward. (c) keeps the duplication 2.2 and 2.4 deferred to this step. (b)
  follows decision 9 (generic numerics apart from models) and 2.4's D1 precedent: a numerical
  method in `numerics/`, not a cross-lab abstraction. **Flag for review (angle c):**
  `CLAUDE.md` says a shared abstraction needs "real models from at least two labs"; this plan
  reads `numerics/` as outside that rule, as 2.4 did; if the reviewers disagree, it is a stop
  for the author.
- **D2. The new user that makes the driver generic.** (a) **the simulated resonance curve,
  sweeping the drive frequency ω** (assigned to 2.5 by the 2.3 plan); (b) a range-against-c or
  range-against-v₀ sweep for a projectile; (c) best angle against drag strength. (a) sweeps a
  non-angle variable of another model, has exact references (R1-R4) and was explicitly
  deferred here. (b) adds little science; (c) is a capability-map item with no Phase 2 step
  (`ROADMAP.md:33`), not added (Not done).
- **D3. The driver's interface** (`numerics/sweep.py`, no physics, no Pydantic).
  `sweep_grid(grid, evaluate) -> list[T]`; `refine_maximum(objective, grid, values, xatol) ->
  (x_best, f_best, i_grid)` (Brent on `[grid[i-1], grid[i+1]]`, grid point kept when it
  beats the refinement: the exact logic of `angle_sweep.py:115-127`);
  `interior_peaks(values) -> int`; `curvature(values, i, step) -> float | None` (centred
  second difference, `None` at an edge or when not bent down); `WorkBudget(limit)` with
  `charge(n)` raising a driver exception the model turns into its own `ModelDomainError`
  message (so the quadratic sweep's messages stay word for word). The model supplies the
  objective, units and messages. Grids are passed in; the driver never builds them.
- **D4. Moving the two angle sweeps.** (a) **both onto the driver, bit-identical, no version
  bump** (three users); (b) only the quadratic one. (a) removes the duplication the 2.2 plan
  recorded. Order inside slice 2: move, then golden digests and all existing sweep tests
  before anything else. One existing test changes one line: the patch target of
  `test_grid_point_is_kept_when_it_beats_the_refinement`
  (`backend/tests/physics/test_quadratic_angle_sweep.py:309`, `qas.minimize_scalar`) moves to
  `simforge.numerics.sweep.minimize_scalar`; its assertions are unchanged. Option not taken:
  injecting the minimiser as a parameter only to keep that line (a seam for a test alone).
  `qas._aggregate` (used by the test at `:824`) stays importable under that name.
- **D5. Check aggregation over runs.** `_aggregate` (`quadratic_angle_sweep.py:332`) gets a
  second user. **Move it to `physics/sweep_checks.py`**, a physics-internal module with two
  physics users (the precedent is `physics/projectile/landing.py`), not to `core/` (one lab
  only). Alternative: repeat it in the resonance module.
- **D6. Resonance sweep inputs** (SI): `mass` kg, `spring_constant` N/m,
  `damping_coefficient` kg/s (> 0), `drive_amplitude` N (> 0), `omega_min`, `omega_max`
  rad/s (0 < min < max ≤ 1e4, the 2.3 bound), `n_frequencies` (3 to a cap set in slice 4),
  `settle_tolerance` ε_s (default 1e-6, bounds [1e-12, 1e-2]; the wait is an experimental
  choice the page explains), `solver` with **DOP853 or RK45 only**. Every run starts from
  rest (x₀ = v₀ = 0), the standard way a resonance curve is measured. **Underdamped only**
  (ζ < 1, so R5's envelope exists); 2.3's Q ≤ 1e4 holds. Radau is excluded: an underdamped run
  is not stiff (2.3's stiffness number guards stiff runs), and Radau's ~3x cost per evaluation
  would set the budget. Alternatives: allow Radau (lower budget for all), user x₀, v₀ (Not done).
- **D7. Each point.** For each ω: the settle time t_s is the smallest whole number of drive
  periods with 2R(ω)e^{−γt_s} ≤ ε_s A(ω) (R5); the run lasts t_s + N_W drive periods
  (N_W = 2, a named constant); it is a call to the 2.3 model through a new
  `run_with_solution` that returns the computation and the `OscillatorSolution` (`run` becomes
  a wrapper; the `physics.oscillator` golden digest must stay unchanged), so each point is
  bit-identical to a 2.3 run of that duration and carries its 2.3 checks. Before any solve,
  every grid point's cycles (max(ω₀, ω)·duration/2π) are checked against 2.3's
  `MAX_CYCLES` and refused naming the worst ω, as 2.2 checks the 2.1 rules first.
- **D8. Extraction.** Lock-in (R3) on M = 64 samples per drive period over the N_W window,
  taken from the dense output (`OscillatorSolution.sample`): c, s, A_sim = hypot(c, s),
  δ_sim = atan2(s, c) ∈ [0, π]. The same extraction on the exact x(t) at the same times gives
  A_ext (extraction and transient only). M and N_W are named constants justified in a comment
  (R3 holds for any M ≥ 3; 64 keeps the trapezoid sum of the dense-output interpolant well
  resolved; measured in slice 3).
- **D9. Peak.** `refine_maximum` on A_sim(ω) (each evaluation one more run, charged to the
  budget), with `xatol` = 1e-7·ω₀ rad/s (2.2's relative precision argument: ω_peak is known
  only to ~√ε of A). u = 2√(ε_A/K) in rad/s, ε_A = the point's bound B1 (below) at the peak;
  an **estimate, not a bound**, `null` with a reason at an edge or with no downward bend; the
  exact ω_r and A_max (R2) shown beside it, `null` when ζ ≥ 1/√2 (no interior peak). The
  response reports Δω/γ and a note when Δω > γ (peak under-resolved).
- **D10. Sweep checks** (`ValidationCheck`, decision 12; 2.3's per-run checks aggregated per
  check id with D5). New, per point, reported as the worst point with its ω:
  **C1** |A_sim − A| ≤ B1 = 2·e_x + ε_s·A + r_A, with e_x the max |x_num − x_exact| over the
  window samples (measured against the exact solution) and r_A a rounding allowance c·M·N_W·ε·A
  (c justified by measurement); a proved inequality given e_x (R3, R5, triangle inequality),
  not a tuned threshold. **C2** |δ_sim − δ| ≤ B1/A (same argument, angle of a perturbed
  vector, valid while B1 < A/2; `passed = null` otherwise). **C3** extraction alone:
  |A_ext − A| ≤ ε_s·A + r_A. **C4** power balance |sin δ_sim − bωA_sim/F₀| ≤ B1/A·(1 + bω/F₀·A)
  (independent of the closed form; bound derived in slice 3 and stated in SV). **C5** the
  refined peak: |ω_peak − ω_r| ≤ max(u, xatol), an estimate, labelled observed; `passed =
  null` when u or ω_r is `null`. Above 100% of a bound gives `passed = false`.
- **D11. Budget.** `MAX_RESONANCE_SWEEP_RHS_EVALUATIONS`, a server constant charged after each
  run (one run may overshoot, as in 2.2), set by measurement in slice 4 against the 30 s proxy
  ceiling (the 2.2 and 2.3 method: slowest refusal on one machine, half the ceiling for a 2x
  slower machine). Estimate before measuring (labelled): DOP853 at 7-10 µs per evaluation
  (`model.py:166`) allows about 1e6 in 10 s. Defaults (m = 1 kg, k = 25 N/m, b = 1 kg/s,
  so ζ = 0.1, Q = 5; F₀ = 1 N; ω from 0.5 to 15 rad/s; n = 21; DOP853 at a tolerance chosen
  so the default fits the budget) are fixed after the measurement.
- **D12. Response, stored summary, replay, golden run.** Response: `model`, `parameters`,
  `solver`, `units`, `assumptions`, `angular_frequencies`, `amplitudes`, `phase_lags`
  (numerical), `exact_amplitudes`, `exact_phase_lags`, `settle_times`, per-point bounds B1,
  the exact formula curve (2.3's `resonance_curve`, for the dashed line), `peak` (refined ω and
  A, u and its note, exact ω_r and A_max or `null`), `grid_step_over_gamma`, `n_rhs_evaluations`,
  `checks`. Summary: refined peak ω and A, worst C1 ratio. Replay: bit-identical on the same
  machine; across platforms the peak within max(xatol, u) (2.2's rule) and amplitudes within
  their B1. Golden case appended to `tests/api/test_registry.py`; no existing digest changes.
- **D13. Frontend.** `SweepPanel`/`SweepAdapter` generalised from angles to any swept variable
  (label, unit, grid fields), the two angle panels unchanged in behaviour; a new
  `ResonanceSweepPanel.tsx` on `/physics/oscillator` (simulated points over the dashed exact
  curve, refined peak with u, exact ω_r, ChecksTable, "Sweeping…"). No cross-model overlay
  (decision 17).
- **D14. Docs.** SV section `physics.oscillator.resonance_sweep` v1.0.0 (references, bounds,
  measured budget and timings, observed results); SV notes under both angle sweeps that the
  duplication is gone; `ARCHITECTURE.md` decision 22 and an edit to decision 19's last
  bullet; README endpoint; `docs/LEARNING_GUIDE.md` Part 22 (~250 lines: lock-in, waiting out
  a transient, power balance, generic driver; exercises without solutions) and Part 19's
  excerpts re-pointed (`LEARNING_GUIDE.md:2525`, `:4186`, `:4235`, `:4289` cite lines that
  move); `docs/briefs/2.5.md`; ROADMAP 2.5 ✅.

## Reference formulas (to be derived on paper in slice 3 and checked by the reviewers)
With ω₀ = √(k/m), γ = b/2m, f = F₀/m, x_p = A cos(ωt − δ):
- **R1** A(ω) = f / √((ω₀² − ω²)² + (2γω)²); tan δ = 2γω/(ω₀² − ω²), δ ∈ [0, π]; A(0) = F₀/k;
  A ~ F₀/(mω²) as ω → ∞. (2.3, proved and tested.)
- **R2** ω_r = √(ω₀² − 2γ²), A_max = f/(2γω_d), ω_d = √(ω₀² − γ²), when ζ < 1/√2. (2.3.)
- **R3** For t_j = t_s + jT/M, j = 0..NM − 1, T = 2π/ω, M ≥ 3: (2/NM)Σ cos²(ωt_j + φ) = 1 and
  (2/NM)Σ cos(ωt_j + φ) sin(ωt_j + φ) = 0, so c = A cos δ and s = A sin δ exactly for
  x = A cos(ωt − δ) (sum of a full set of M-th roots of unity of e^{2iωt_j} is 0 for M ∤ 2).
- **R4** Steady state, mean over a period: ⟨F₀ cos ωt · ẋ⟩ = ½F₀ωA sin δ and ⟨bẋ²⟩ = ½bω²A²;
  equal, so sin δ = bωA/F₀.
- **R5** For any signal error e_j, |(c, s) error| ≤ (2/NM)Σ|e_j| ≤ 2 max|e_j|; with the
  transient |x − x_p| ≤ R e^{−γt} (2.3, proved), the transient adds at most 2R e^{−γt_s} to A.

## Seams (where tests attach; what each catches and misses)
1. **Driver** (`numerics/sweep.py`): synthetic objectives with known maxima. *Catches*
   bracketing, fallback, edge, budget and curvature errors. *Misses* any model.
2. **Refactor** (angle sweeps): golden digests and all existing sweep tests. *Catches* any
   change of numbers or messages. *Misses* new behaviour (there is none).
3. **Extraction** (`physics/oscillator/resonance_sweep.py`, lock-in and settle time): R3, R5
   on synthetic signals. *Catches* factor, sign, window and settle errors. *Misses* the solver.
4. **Model run and checks**: R1, R2, R4 against the closed forms; mutants; corner grids.
   *Catches* assembly and bound errors. 5. **API and registry**: 422s, budget, golden, replay,
   contract. 6. **Frontend**: Vitest, Playwright; *misses* science (seams 1-4).

## Slices (test-first with `tdd`)
Common commands (from the root): `scripts/run_logged.sh lint 'cd backend && uv run ruff check
. && uv run ruff format --check . && uv run mypy'`. "Full pytest" is
`scripts/run_logged.sh <slice>-pytest 'cd backend && uv run pytest -q'`; its only allowed
failures are the 6 known-red A2 tests in `backend/tests/physics/foundations/test_core_momentum.py`
(`docs/HANDOFF.md`, "Known red"; the author's, never touched). "No existing test changed"
means `git diff --stat --diff-filter=MDR HEAD -- backend/tests` lists only the files the slice
names.

### Slice 1: the sweep driver (risky: numerics; `test-writer-risky`, `builder-risky`, 1 `reviewer`)
`numerics/sweep.py` (D3), not yet used by any model; SV: a short `numerics/` note.
**Acceptance.**
- **Test files (new):** `backend/tests/numerics/test_sweep.py`.
- **Commands:** `scripts/run_logged.sh s1-sweep 'cd backend && uv run pytest
  tests/numerics/test_sweep.py -q'` (red before, green after); full pytest; the common
  commands; the `git diff` above (prints nothing).
- **Checks:** (1) On f(x) = −(x − x*)² with x* off-grid, `refine_maximum` returns x* within
  `xatol` and, with a stand-in minimiser that returns the bracket's left end, keeps the grid
  point? (2) A maximum at either grid edge refines inside the edge interval and `curvature`
  returns `None` there; on a parabola of known K it returns K to 1e-12 relative (second
  difference of a quadratic is exact up to rounding, justified in the test)? (3) `interior_peaks`
  counts 0, 1 and 2 on hand-made sequences, plateaus not counted? (4) `WorkBudget` raises on the
  first charge that exceeds the limit and not before? (5) Full pytest (only the known red),
  ruff, format and mypy pass, and no existing test file changed?

### Slice 2: both angle sweeps on the driver (risky: refactor of validated models; `builder-risky`, 1 `reviewer`)
Order: (a) `angle_sweep.sweep` and `quadratic_angle_sweep.sweep` call the driver; `_aggregate`
moves to `physics/sweep_checks.py` (D5) and stays importable as `qas._aggregate`; the one-line
patch-target change (D4). Then (b) golden digests and all sweep tests. Then (c) guide Part 19
excerpts re-pointed, `ARCHITECTURE.md` decision 19's duplication note updated, SV limitation
at `SCIENTIFIC_VALIDATION.md:1111-1112` removed. No version bump.
**Acceptance.**
- **Test files:** changed only `backend/tests/physics/test_quadratic_angle_sweep.py` (line
  309's patch target). Unchanged and passing: `backend/tests/physics/test_angle_sweep.py`,
  `backend/tests/physics/test_quadratic_angle_sweep.py` (all other lines),
  `backend/tests/api/test_angle_sweep_api.py`, `backend/tests/api/test_quadratic_angle_sweep_api.py`,
  `backend/tests/api/test_quadratic_angle_sweep_limits.py`,
  `backend/tests/physics/test_projectile_checks.py`, `backend/tests/api/test_golden_digests.py`.
- **Commands:** `scripts/run_logged.sh s2-sweeps 'cd backend && uv run pytest
  tests/api/test_golden_digests.py tests/physics/test_angle_sweep.py
  tests/physics/test_quadratic_angle_sweep.py tests/api/test_angle_sweep_api.py
  tests/api/test_quadratic_angle_sweep_api.py tests/api/test_quadratic_angle_sweep_limits.py
  tests/physics/test_projectile_checks.py -q'`; `git diff --stat backend/tests` (one file, one
  line); `git diff backend/tests/api/golden_runs.json` (prints nothing);
  `scripts/run_logged.sh s2-excerpts 'python3 scripts/check_excerpts.py'`; full pytest; the
  common commands.
- **Checks:** (1) Every golden digest is unchanged, both sweeps at their current versions
  (1.1.0 and 1.0.1)? (2) Every listed sweep test passes, the budget and guard messages
  included word for word? (3) `angle_sweep.py` and `quadratic_angle_sweep.py` no longer contain
  their own Brent call or grid-maximum logic (`grep -n minimize_scalar` finds it only in
  `numerics/sweep.py`)? (4) `check_excerpts.py` passes and Part 19 still shows the refinement
  code it explains? (5) Full pytest (only the known red), ruff, format, mypy pass?

### Slice 3: the resonance sweep model (risky: scientific core, tolerances; `test-writer-risky`, `builder-risky`, 1 `reviewer`)
`physics/oscillator/model.py`: `run_with_solution` (D7; `run` a wrapper, digest unchanged);
new `physics/oscillator/resonance_sweep.py` (settle time, lock-in, sweep on the driver,
peak, checks C1-C5, `MODEL_INFO`, `UNITS`, `ASSUMPTIONS`, `run`); R3-R5 written out in the
module docstring; SV section started (references, bounds, observed extraction error).
**Acceptance.**
- **Test files (new):** `backend/tests/physics/test_resonance_sweep.py` (R3 on synthetic
  sinusoids for M ∈ {3, 4, 64} and arbitrary phase; R5 on a sinusoid plus a known decaying
  term; settle time is the smallest whole period count satisfying R5; R1 and R2 at the default
  and on a corner grid (ζ ∈ {0.01, 0.1, 0.5, 0.9}, ω from 0.05ω₀ to 20ω₀ within the cycles cap);
  R4 at every point; two mutants: factor 1/NM instead of 2/NM, sine projection with the wrong
  sign; a stiff or overdamped input refused before any solve). Unchanged and passing:
  `backend/tests/physics/test_oscillator_model.py`, `backend/tests/api/test_oscillator_api.py`.
- **Commands:** first `scripts/run_logged.sh s3-golden 'cd backend && uv run pytest
  tests/api/test_golden_digests.py tests/physics/test_oscillator_model.py -q'` after
  `run_with_solution` alone (all pass, `physics.oscillator` digest unchanged); then
  `scripts/run_logged.sh s3-resonance 'cd backend && uv run pytest
  tests/physics/test_resonance_sweep.py -q'`; full pytest; the common commands.
- **Checks:** (1) After `run_with_solution` alone, every golden digest is unchanged? (2) R3:
  the lock-in of A cos(ωt − δ) returns A and δ within c·ε (c stated) for every M ≥ 3 tested,
  and R5's bound holds and is reached within a factor 2 on the synthetic transient? (3) On the
  default and the corner grid, C1-C4 pass at every point, the exact A(0) and high-frequency
  limits are approached as R1 says, and the refined peak is within max(u, xatol) of ω_r where
  ζ < 1/√2? (4) Each mutant fails C1 or C4 while the true code passes? (5) Full pytest (only
  the known red), ruff, format, mypy pass, and no existing test file changed?

### Slice 4: API, limits and budget (risky: inputs and limits; `builder-risky`, `/security-review`)
Schemas (D6, strict, finite, units), route `POST /api/v1/physics/oscillator/resonance-sweep`,
`ModelEntry`, registry, response union (`api/outputs.py`), golden case appended,
`make api-types`; budget and `n_frequencies` cap measured (D11) and recorded in SV with
machine, versions and the slowest refusal.
**Acceptance.**
- **Test files (new):** `backend/tests/api/test_resonance_sweep_api.py` (default run, saved and
  replayed identical, stored inputs rebuild the request), `backend/tests/api/test_resonance_sweep_limits.py`
  (422 for NaN, ±Infinity, b = 0, F₀ = 0, ζ ≥ 1, min ≥ max, n out of range, Radau, a grid over
  `MAX_CYCLES` naming the worst ω, and the budget naming the evaluations; each message says what
  to change; the slowest admitted and refused requests within the measured time); appended case
  in `backend/tests/api/test_registry.py`; `backend/tests/api/golden_runs.json`.
- **Commands:** `scripts/run_logged.sh s4-api 'cd backend && uv run pytest
  tests/api/test_resonance_sweep_api.py tests/api/test_resonance_sweep_limits.py
  tests/api/test_registry.py tests/api/test_golden_digests.py -q'`; `cd backend && uv run python
  -m tests.api.pin_golden_runs` then `git diff backend/tests/api/golden_runs.json`; `make
  api-types` then `scripts/run_logged.sh s4-tsc 'cd frontend && npx tsc --noEmit'`; full
  pytest; the common commands.
- **Checks:** (1) Every listed refusal is a 422 naming the number to change, before any solve
  where the rule allows it? (2) The golden diff only appends `physics.oscillator.resonance_sweep`
  1.0.0 and no other digest changes? (3) The budget and the `n_frequencies` cap are named
  constants whose comments cite the measurement recorded in SV, and the slowest refusal is under
  half the 30 s proxy limit? (4) A saved run replays "identical" and reopens from stored inputs?
  (5) The regenerated contract is in the slice, `tsc` passes, and full pytest (only the known
  red), ruff, format, mypy pass?

### Slice 5: frontend (routine: `test-writer`, `builder`)
D13; e2e and stored-fields case; `lib/export/tables.ts`, `lib/reference/overlay.ts`,
`lib/reference/compare.ts` entries (ARCHITECTURE, "Adding a new model", step 4).
**Acceptance.**
- **Test files:** new `frontend/src/components/ResonanceSweepPanel.test.tsx`, new
  `frontend/e2e/resonance-sweep.spec.ts`; updated `frontend/src/components/AngleSweepPanel.test.tsx`
  (generalised adapter, behaviour unchanged), `frontend/src/components/OscillatorLab.test.tsx`,
  `frontend/e2e/stored-fields.spec.ts`.
- **Commands:** `scripts/run_logged.sh s5-vitest 'cd frontend && npx vitest run
  src/components/ResonanceSweepPanel.test.tsx src/components/AngleSweepPanel.test.tsx
  src/components/OscillatorLab.test.tsx'`; `scripts/run_logged.sh e2e 'scripts/check.sh --e2e'`.
- **Checks:** (1) The panel runs the default, shows simulated points over the dashed exact
  curve, the refined peak with u and the exact ω_r, and its ChecksTable? (2) Both angle-sweep
  panels behave as before (their tests pass with only the adapter's shape changed)? (3) A
  resonance-sweep run saves, reopens and appears in the stored-fields case? (4)
  `scripts/check.sh --e2e` passes in full (only the known red)?

### Slice 6: docs, guide, brief and close-out (routine: `builder`)
D14; `docs/HANDOFF.md`; this plan's status.
**Acceptance.**
- **Files:** `SCIENTIFIC_VALIDATION.md`, `ARCHITECTURE.md`, `README.md`, `ROADMAP.md`,
  `docs/LEARNING_GUIDE.md`, `docs/briefs/2.5.md`, `docs/INDEX.md` (regenerated).
- **Commands:** `scripts/run_logged.sh s6-docs 'python3 scripts/check_excerpts.py && python3
  scripts/doc_index.py --check'`; `scripts/run_logged.sh e2e 'scripts/check.sh --e2e'`.
- **Checks:** (1) Excerpts and index checks pass? (2) Part 22 explains the lock-in, the settle
  time, the power balance and the driver with checkpoints and exercises without solutions, in
  about 250 lines? (3) SV labels every claim of the new model proved (R1-R5, C1-C3 bounds),
  tested or observed (C5, u, budget timings)? (4) ROADMAP 2.5 is ✅ with this plan's path and no
  other row changed; ARCHITECTURE decision 22 exists; README lists the endpoint; the brief labels
  every claim?

## Risks
- **Cost** (largest): settle time grows like ln(1/ε_s)·Q/π cycles near ω₀ and with ω above
  it; a 21-point sweep plus ~10-15 Brent runs may not fit a budget near 1e6 at tight
  tolerances. Measured in slice 4; refusals say what to change (fewer points, looser ε_s or
  tolerance, lower Q). If even the default cannot fit at an honest tolerance, that is a stop
  for the author (smaller defaults or a narrower model), not a quiet loosening.
- **Refactor not bit-identical**: Brent's bounds or call order changing a last bit; the golden
  run in slice 2 is the guard, and a mismatch is fixed, not re-pinned.
- **Dense-output error** in the window can exceed the node error the 2.3 checks measure; C1
  measures e_x at the window samples themselves, so the bound stays honest.
- **R5 near critical damping**: R grows like 1/ω_d (`analytical.py:632-634`); only ln R enters
  t_s, but cycles may hit `MAX_CYCLES` for ζ close to 1; refused before any solve.
- **C4's bound** is derived in slice 3; if it cannot be made rigorous it is labelled a measured
  threshold (1-2-5 rule, ≥ 10x the worst) in SV, not presented as proved.
- **Unverified:** R3-R5 numerically; every constant, cap and timing (measured in slices).

## Out of scope / Not done
- **Best angle against drag strength** and **drag-law comparison** (capability map Core,
  `ROADMAP.md:33`, no Phase 2 step): not added; they stay an open decision in `docs/HANDOFF.md`.
- A sweep of any input of any model (D1a) and tornado charts: Phase 3 ("Sensitivity and
  uncertainty"); a cross-lab sweep layer is extracted then, with the second lab's real model.
- Two-parameter sweeps and heatmaps (Quant Lab overfitting heatmaps, Phase 6).
- Resonance sweeps from a chosen initial state, with Radau, of the undamped or overdamped
  oscillator, or of the nonlinear pendulum (Ext); the half-power width (Q = ω₀/Δω) read off the
  simulated curve; sweep progress reporting; parallel runs or a job queue (Phase 7, only if
  measured).
- Fixed-step studies of the damped or driven oscillator (open decision in `docs/HANDOFF.md`,
  2.4's Not done).
- Animation (2.6).

## Genuine stops found
None, with one flag. Checked: no new dependency (`backend/pyproject.toml:12-13`); no roadmap
scope or order change (the work maps to the 2.5 row, the Phase 2 text and what the 2.2 and 2.3
plans assigned to 2.5; the two unscheduled capability-map items are not added); Track A and
`backend/physics/foundations/` untouched; no new storage of user data, auth or network access;
stored runs unchanged (no version bump; one new model appended); no guard-rail file touched;
every scientific claim has an independent reference (R1-R5, closed forms validated in 2.3) or
is labelled an estimate (u, C5). **Flag (D1):** the "two labs" wording in `CLAUDE.md`
Standards and `ROADMAP.md:18` versus a `numerics/` driver used by three Physics models;
reviewer angle (c) decides whether this needs the author.
