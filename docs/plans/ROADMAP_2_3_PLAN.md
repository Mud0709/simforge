# Roadmap 2.3 plan: simple, damped and driven oscillators (grilled with the author)

Drafted on 2026-11-02 by a planning subagent (decided by default, D1-D17), then **grilled with
the author on 2026-11-03** in three rounds; the author accepted every decision with the
amendments below (G1-G4), which take precedence over the text of the decisions they modify.

## Grilling record (2026-11-03)
- **Round 1:** D1 one model with UI presets; D2 SI inputs and the Damped defaults; D4 adaptive
  solvers only (symplectic methods in 2.4, where the author writes them); D9 the formula
  resonance curve (the simulated one in 2.5). **G1:** Claude builds slices 1-5 test-first,
  scientific core (slices 1-3) with an Opus worker and a fresh Opus review each.
- **Round 2:** D3 the unified exact form with pitfalls (i)-(iii) tested; D6 limits provisional,
  measured in slice 2; D7 the three independent references; D10 exact Q with the IB energy
  ratio labelled approximate ("IB definition"); D11 a new package and route module.
  **G2 (amends D5):** the scale X also includes the **predicted** amplitude, an exact formula
  of the inputs: X = max(|x₀|, |v₀|/ω₀, A, B_max), with A the steady-state amplitude (OR1) when
  b > 0 and B_max the bound of the undamped driven part over the run (OR3) when b = 0. The plan's
  X was F₀/k at resonance while the motion is Q·F₀/k, which made every check Q times stricter
  than intended.
- **Round 3:** D8 checks with measured thresholds; D12 stored fields; D13 replay tolerances
  (step counts exact until the separate open decision); D14 the page; D15 the 1.6 wiring; D16
  docs (Part 20 ≈ 250 lines, IB claims checked against `docs/IB_FOUNDATIONS.md`).
  **G3 (amends D6 and D3 iv):** no Q limit unless slice 1 measures the exact solution's error
  near resonance at Q = 1e4, 1e6, 1e8 above 1e-12 of X; then the limit is the measured edge.
  **G4:** each slice ends with this plan's status updated and its documentation written.

## Slice status
- **Slice 1 (exact solution): done 2026-11-03.** `physics/oscillator/analytical.py` and 317
  tests against a 90-digit reference; fresh Opus review in three passes, all findings fixed;
  documented in `SCIENTIFIC_VALIDATION.md`. Amendments from the review, decided by the author:
  **A (reverses G3):** Q ≤ 1e4 when b > 0, because the error relative to the motion actually
  reached grows like ε·Q. **B (replaces G2's formula):** X = √(x₀² + (v₀/ω₀)²) + D, a proved
  upper bound on |x| over the run (D: the smallest of six proved caps on the driven part).
  **Under D6's measured limits:** a minimum duration max(ω₀, ω, γ)·T ≥ 1, enforced at the API
  in slice 3. Error model (measured): c·ε·(Q + ω₀T + A/X + 1)·X with c ≤ 1.5. For slice 2:
  checks are scaled by this X; velocity scale V = ω₀X (author, 2026-11-09; this note first said
  max(ω₀, ω)·X); the Q = 1e4 resonance error
  (≈ 6e-12 of X) is the exact solution's own floor.
- **Slice 2 (numerical solve and run): built 2026-11-10, fresh review done (no must-fix; 7 worth-doing items in the 2026-11-10 journal, to settle before slice 3).**
  `numerical.py`, `model.py`, `schemas.py`; the 250 tests written first pass. Measured on 1608
  runs (`SCIENTIFIC_VALIDATION.md`): thresholds `F (rtol + atol)(1 + cycles) + 1e-9`, F = 50,
  500, 2e4, 1e3, 20 (displacement, velocity, energy, period, ratio), worst 0.10 of a threshold.
  **N_max = 500 cycles** (D6's 2 s at the default settings; D6 said 1000). Builder's choices,
  open for the author: the energy factor is set by drives at 100ω₀ (speed 50 V), so it is
  loose for slow motions; free-decay checks need x₂ ≥ 1e-3 X; Radau (36-78 s at 500 cycles,
  default pair) needs a cost rule beyond N_max before slice 3 exposes it.
- Slices 3-5: not started.

**Scope: the 2.3 row**, "Simple, damped and driven oscillators", read with the capability
map's Oscillators row (Core: "simple, damped and driven harmonic oscillator, resonance
curve"). In scope: one linear oscillator covering all three cases, its exact solution, an
adaptive numerical solution checked against it, and the **exact** resonance curve of the driven
case (D9). Out of scope: fixed-step and symplectic methods and energy drift (2.4), a
*simulated* resonance curve (2.5), animation (2.6), the nonlinear pendulum (Ext). Track A's P5
(IB SHM) stays planned unchanged; 2.3 neither builds nor replaces it.

**The fact that drives most choices:** unlike quadratic drag, this model has an exact solution
for every input. So the projectile pattern applies (exact against numerical, decision 2), and
the hard parts are **evaluating the exact solution accurately in every regime** (four
numerical pitfalls, D3) and **choosing scales** so the solver tolerances mean the same thing
from a 1 mg mass to a 1 t mass (D5).

## What 2.3 builds
A new page, `/physics/oscillator`: a mass on a spring, with optional damping (a force against
the velocity, the same `F = −bv` as linear drag) and an optional driving force `F₀ cos ωt`.
Three preset buttons fill the form: **Simple** (no damping, no drive: the IB SHM case),
**Damped** (light damping; heavier damping by raising b) and **Driven** (damped, driven at the
natural frequency). Each run shows the displacement over time (numerical, with the exact
solution dashed and, when damped, the decay envelope), the energy over time (kinetic,
potential, energy removed by damping, energy put in by the drive), and, when driven, the
**resonance curve**: the steady-state amplitude and phase lag against drive frequency, from
the formula, with this run marked on it. Results list ω₀, the period, the damping ratio ζ, the
regime (under-, critically or overdamped), Q, and the steady-state amplitude and phase.
Validation shows how far the simulation strays from the exact answer, the energy balance, and,
for a free damped run, the measured period and peak-to-peak decay against their formulas. Runs
save, replay, recompute, export and compare like every other model.

## Design tree and rounds (self-grilled)
- **Round 1** (no prerequisites): D1 one model or three; D2 equation, inputs and units;
  D4 which integrators; D9 what "driven" includes.
- **Round 2**: D3 how the exact solution is evaluated; D5 scaling and tolerances; D6 limits;
  D7 validation references; D10 Q factor; D11 code layout.
- **Round 3**: D8 per-run checks; D12 response, summary, hash; D13 replay and golden run;
  D14 UI; D15 the 1.6 wiring; D16 docs and guide; D17 seams for `tdd`.

Each decision lists the options, the **default taken** (bold) and why. Reversal: every
default can be changed before slice 1; after it, by editing the slice that owns it.

## Decisions
- **D1. One model or three?** (a) three models (simple, damped, driven); (b) one model with a
  `kind` field; (c) **one model, `physics.oscillator` v1.0.0**, "Harmonic oscillator (simple,
  damped, driven)", `POST /api/v1/physics/oscillator/simulate`, where simple and damped are
  b = 0 and F₀ = 0. One equation and one exact solution cover all three, and there are no
  stored runs to protect (unlike 2.1, decision 18). (a) triples routes, entries and pages for
  one equation; (b) adds a field that can contradict the numbers (kind "simple" with b > 0).
  The presets are UI-only: they fill fields, nothing stored records them. The id leaves room
  for `physics.oscillator.pendulum` (Ext).
- **D2. Equation, inputs and units.** `m ẍ + b ẋ + k x = F₀ cos ωt`, drive phase 0 at t = 0.
  Inputs (SI, physical, as the projectile's): `mass` kg, `spring_constant` N/m,
  `damping_coefficient` kg/s, `drive_amplitude` N, `drive_angular_frequency` rad/s,
  `initial_displacement` m, `initial_velocity` m/s, `duration` s. Derived and shown, never
  input: ω₀ = √(k/m), γ = b/2m, ζ = b/(2√(mk)), Q = √(mk)/b, f = ω/2π. Options not taken:
  dimensionless inputs (ω₀, ζ, ω/ω₀): fewer fields, but the IB writes `ω = √(k/m)` and the
  link to the projectile's b is lost; frequency in Hz: every formula is in ω, so the UI shows f
  beside it instead. **Defaults** (the Damped preset): m = 1 kg, k = 25 N/m (ω₀ = 5 rad/s,
  T ≈ 1.26 s), b = 0.5 kg/s (ζ = 0.05, Q = 10), F₀ = 0, ω = 5 rad/s, x₀ = 0.1 m, v₀ = 0,
  duration 20 s (about 16 periods).
- **D3. Evaluating the exact solution** (formulas below). One **unified form** for all three
  regimes, x = x_p + e^{−γt}[x̃₀C(t) + (ṽ₀ + γx̃₀)S(t)], with C, S the cos/1/cosh and
  sin/t/sinh functions of q = ω₀² − γ² (computed as (ω₀ − γ)(ω₀ + γ)). Four pitfalls handled:
  (i) **0/0 at critical damping** in the branch formulas: S = t·sinc(√q t) is continuous
  through q = 0, so "critically damped" is only a label (exactly when b² = 4mk in floats);
  (ii) **overflow** of e^{−γt}cosh(βt) for heavy damping (βt > 710): use the two-exponential
  form with the slow rate written **ω₀²/(γ + β)**, not γ − β (cancellation when ζ ≫ 1);
  (iii) **undamped driving near resonance**: x_p and the transient are huge and nearly cancel,
  so b = 0 uses the beat form (cos ωt − cos ω₀t)/(ω₀² − ω²) rewritten with a sinc, which is
  also exact **at** ω = ω₀ (linear growth t sin ω₀t / 2ω₀); (iv) **light damping near
  resonance** has the same cancellation, with rounding of order ε_mach·Q·F₀/k: bounded by the
  input rule Q ≤ 1e4 for b > 0 (D6). Options not taken: separate branch formulas per regime
  (the 0/0 and overflow); a divided-difference/matrix-exponential form that is stable
  everywhere with no Q limit (too far beyond IB to explain; kept as the reversal of the Q
  limit). The guide explains (i)-(iii) as a numerical-analysis lesson, like the projectile's
  cancellation (`SCIENTIFIC_VALIDATION.md:53`).
- **D4. Which integrators.** (a) **SciPy `solve_ivp` through the shared `SolverSettings`
  (RK45, DOP853, Radau) unchanged**, as 2.1 and 2.2 do; (b) also the from-scratch Euler/RK4
  of `numerics/fixed_step.py`; (c) also symplectic Euler and Verlet. **(a)**. Fixed-step and
  symplectic methods, and long-run energy drift, are exactly roadmap 2.4 ("the methods workbench
  for any time-stepping model"); the oscillator is built so 2.4 can plug in (seam 1 exposes a
  pure right-hand side and the exact state). This also keeps open the learning guide's
  suggestion that the author writes the symplectic oscillator himself
  (`docs/LEARNING_GUIDE.md:2439-2442`). Radau stays for heavily overdamped (stiff) runs.
- **D5. Scaling and the meaning of atol.** (a) integrate in SI with a 2.1-style rule
  `atol ≤ 1% of the smallest scale`; (b) **integrate the dimensionless form** τ = ω₀t,
  ξ = x/X, η = v/(ω₀X), with the two work integrals divided by kX², and return SI. **(b)**:
  every state component is then of order 1, so `rtol`/`atol` mean the same thing at every
  scale, and 2.1's slow-run pathology (atol far above a velocity scale, quadratic_schemas.py
  15-21) cannot occur; no atol rule is needed. X is a **scale from the inputs, never from the
  solution**: X = max(|x₀|, |v₀|/ω₀, F₀/(m·ω₀·max(ω₀, ω))), which is F₀/k up to resonance and
  the size of the from-rest transient F₀/(mωω₀) above it. `units` states "atol: dimensionless,
  a fraction of the scale X (m)". Cost: one more idea to explain (scaling; the guide does). A
  run where x₀ = v₀ = F₀ = 0 has X = 0 and is refused (nothing moves).
- **D6. Limits** (provisional; the corners test in slice 3 checks them, measurements in slice 2
  may tighten them). Fields: m 1e-6 to 1e6 kg (the projectile's), k 1e-6 to 1e9 N/m, b 0 to
  1e6 kg/s, F₀ 0 to 1e6 N, ω 0 to 1e4 rad/s, x₀ −1e3 to 1e3 m, v₀ −1e4 to 1e4 m/s, duration
  > 0 to 1e6 s, `n_samples` 10 to 5000 (default 400). Combined rules, each a 422 that says what
  to change: ω₀ from 1e-3 to 1e4 rad/s; γ = b/2m ≤ 1e4 s⁻¹ (`MAX_DRAG_RATE`); ω ≤ 100·ω₀
  (keeps the forced motion within reach of the scale X); **Q ≤ 1e4 when b > 0** (pitfall iv;
  b = 0 is allowed and exact); **at most N_max = 1000 cycles**, `duration·max(ω₀, ω)/2π`
  (cost grows with cycles; provisional, measured in slice 2 against a ≤ 2 s run and the 30 s
  Next.js proxy limit found in 2.2, B2); not all of x₀, v₀, F₀ zero. **Stiffness guard** (a
  ModelDomainError, 422, as `quadratic_model._guard`): explicit methods are refused when the
  fast decay rate times the duration, (γ + β)·T for overdamped runs, exceeds
  `EXPLICIT_STIFFNESS_LIMIT` (1e4); Radau has no such limit.
- **D7. Validation references** (OR1-OR8 below). The exact solution is the main reference for
  the numerical one, so the exact solution is itself tested against **independent** references:
  a 60-digit `decimal` evaluation of the textbook branch formulas (test-side; Taylor series for
  sin and cos, ~20 lines), an independent tight integration with its own right-hand side in the
  test, and limits and identities. **Observed in scratch:** a tight DOP853 solve is **not** a
  good enough reference for heavy damping (at ζ = 4 it differed from the closed form by 7e-11
  of max|x|, while the closed form was within 1.8e-16 m of the 60-digit value), so overdamped
  tests use the `decimal` reference.
- **D8. Per-run checks** (`ValidationCheck`, decision 12): **displacement error** max|x − x_exact|
  / X over the step nodes and **velocity error** likewise / ω₀X (numerical diagnostics,
  against the exact solution); **energy balance** KE + PE + W_damp − W_drive = E₀ with both
  works integrated alongside the motion from b·v² and F₀cos(ωt)·v (coded from those formulas,
  never from the force, as 2.1's W), normalised by kX²; for a **free underdamped** run with at
  least two maxima, the **period between maxima** against 2π/ω_d and the **ratio of successive
  maxima** against e^{−γT_d} (both exact identities, located by an event on v = 0); for a
  **driven damped** run, an informational **"steady state reached"**: the remaining transient
  at the end, computed exactly, as a fraction of A; and an informational **cost** line (cycles,
  evaluations, the guard's stiffness number). Thresholds start from 2.1's form,
  `1e4 × (rtol + atol) + 1e-9` in scaled units, and are **set by measurement in slice 2**; the
  global error of a long run grows with the number of cycles (phase error accumulates), so a
  cycles factor is expected and must be justified by the measurement, not assumed.
- **D9. What "driven" includes.** (a) the driven run only; (b) **the run plus the exact
  resonance curve** (amplitude A(ω) and phase δ(ω) from the formula, 0 to max(3ω₀, 1.2ω), with
  this run's ω marked); (c) also a simulated resonance curve (one run per drive frequency).
  **(b)**: the curve is a closed form, costs no solves, and is how a driven oscillator is read
  (capability map: "resonance curve", Core). (c) is a sweep of runs, which roadmap 2.5
  ("Generic sweeps") owns; recorded under Out of scope. Labelled "formula" on the chart.
- **D10. Q factor.** Shown as Q = ω₀/2γ = √(mk)/b (exact, by definition), with two exact
  facts tested and explained: the **power** resonance curve peaks exactly at ω₀ and its full
  width at half maximum is exactly 2γ, so Q = ω₀/Δω exactly; and the free decay's amplitude
  ratio per period is e^{−γT_d}. "Q ≈ 2π × energy stored / energy lost per cycle" is
  **approximate** (good only for large Q) and is labelled so, with the exact relation beside it.
  The amplitude peak sits at ω_r = √(ω₀² − 2γ²) only when ζ < 1/√2 (exact; there is no peak
  otherwise), shown with A_max = F₀/(2mγω_d).
- **D11. Code layout.** A new package `physics/oscillator/`, following "Adding a new model"
  (`ARCHITECTURE.md:457-471`): `analytical.py` (exact solution, regimes, steady state, resonance
  curve; pure), `numerical.py` (scaled ODE, works, maximum events; pure), `model.py`
  (`MODEL_INFO`, `UNITS`, `ASSUMPTIONS`, scales, guard, checks, series, `run`), `schemas.py`. A
  new route module `api/routes/oscillator.py` with its `ModelEntry` (its router added to the
  tuple in `main.py:50-56`, its entry to `api/registry.py`), rather than appending to the
  736-line `api/routes/physics.py`, which holds only projectile helpers. Reuses `SolverSettings`, `MAX_DRAG_RATE`, `MIN_MASS`,
  `EXPLICIT_STIFFNESS_LIMIT`, `ValidationCheck`, `record_run` via `execute`; changes **no**
  existing model code.
- **D12. Response, stored summary, hashed inputs.** Response: `model`, `parameters`, `solver`,
  `units`, `assumptions`, `derived` (ω₀, γ, ζ, Q or null when b = 0, regime, ω_d or β, T_d or
  null, X), `steady_state` (A, δ, ω_r, A_max; null when undriven or b = 0), `numerical` (final
  x and v, max errors, n_steps, n_rhs_evaluations, method, rtol, atol), `diagnostics`,
  `checks`, `series` (t, x, v, x_exact, v_exact, envelope or null, KE, PE, W_damp, W_drive),
  `resonance` (ω, A, δ; null when undriven), `method_note`, `metadata`. Hashed inputs:
  `parameters`, `solver`, `n_samples` (as 2.1). Stored summary: `derived`, `steady_state`, the
  max displacement, velocity and energy-balance errors, the two free-decay residuals (or null),
  `n_steps`, `n_rhs_evaluations`. Curves are recomputed, not stored (decision 5).
- **D13. Replay tolerances and golden run.** Closed forms (`derived.*`, `steady_state.*`):
  1e-12 relative; `regime`: exact; the error and residual diagnostics: absolute
  `10 × (rtol' + atol)` in scaled units with `rtol' = max(rtol, 1e-10)` (2.1's floor and its
  reason); counts exact (consistent with 2.1; the handoff's open question about step counts
  applies here too and is not decided by this plan). A case is **appended** to
  `tests/api/test_registry.py` (other tests index cases by position) and only its golden entry
  is added; the diff must show the eight existing entries unchanged.
- **D14. UI.** `OscillatorLab.tsx` and `OscillatorResults.tsx` inside `Workspace`, fields from
  `lib/oscillator/fields.ts` via `spec()`; the three presets as buttons above the form; a nav
  link "Oscillators" in `app/layout.tsx` and a card on the home page. Charts: displacement
  (numerical solid, exact dashed "exact (formula)", envelope ±e^{−γt} dotted when damped),
  energy, and the resonance curve (amplitude and phase, this run marked) only when F₀ > 0.
  Results show "numerical", "exact" or "formula" beside every number. Not taken: a phase
  portrait (x against v) and a drive-phase input (cheap later; neither is in the row).
- **D15. 1.6 wiring** (`ARCHITECTURE.md:466-470`): response union (`api/outputs.py`,
  `lib/api/models.ts`); `exportTables` (time series; resonance curve when driven);
  `inputFields`/`summaryFields` (`lib/reference/compare.ts`); `referenceSeries` for the
  displacement and energy charts (`lib/reference/overlay.ts`); `lib/runs/pages.ts`; two
  `e2e/stored-fields.spec.ts` cases (undriven undamped, so the nulls are covered; driven,
  overdamped, Radau, odd `n_samples`).
- **D16. Docs and learning guide.** A new **Part 20** in `docs/LEARNING_GUIDE.md`, "Oscillators:
  springs, damping and resonance", about 250 lines (the author's rule): SHM intuition
  (restoring force, ω = √(k/m), period independent of amplitude, energy swapping) [IB C.1];
  damping, its three regimes and the envelope [IB C.4, detail to verify against the guide];
  driving, resonance and the phase lag 0 → 90° → 180° [IB C.4, verify]; Q and the half-power
  width [verify whether IB; otherwise Beyond IB]; the unified exact solution and pitfalls
  (i)-(iii) [Beyond IB, intuition first]; scaling (D5); the checks; a short code walkthrough
  with `<!-- src: -->` tags; checkpoints and exercises without solutions. Part 10's "After
  that" paragraph (lines 2439-2442) points to Part 20 and to 2.4. Also the Contents, Part 0,
  the symbol table and "Changes". `SCIENTIFIC_VALIDATION.md` (new section),
  `ARCHITECTURE.md` (decision 20, layout, endpoint table), `README.md`, `ROADMAP.md` (2.3 ✅
  with a one-line outcome; capability map Oscillators row). Guide tags in any touched file are
  re-checked by hand (no script checks them).
- **D17. Seams for `tdd`.** As listed below; all five taken as proposed.

## Reference formulas (derived for this plan)
Symbols: ω₀ = √(k/m), γ = b/2m (1/s), ζ = γ/ω₀, Q = ω₀/2γ, f = F₀/m (m/s²), q = ω₀² − γ²,
ω_d = √q (q > 0), β = √(−q) (q < 0), T_d = 2π/ω_d.
- **OR1 Steady state.** x_p = A cos(ωt − δ), A = f/√((ω₀² − ω²)² + (2γω)²),
  δ = atan2(2γω, ω₀² − ω²) ∈ [0, π].
- **OR2 Transient (unified).** With x̃₀ = x₀ − x_p(0), ṽ₀ = v₀ − ẋ_p(0):
  x_h = e^{−γt}[x̃₀C + (ṽ₀ + γx̃₀)S], v_h = e^{−γt}[ṽ₀C − (γṽ₀ + ω₀²x̃₀)S], where
  C = cos ω_d t, 1, cosh βt and S = t·sinc(ω_d t), t, sinh(βt)/β (S′ = C, C′ = −qS; derived by
  hand here). Overdamped, stably: x_h = A₁e^{−s t} + A₂e^{−(γ+β)t}, s = ω₀²/(γ + β).
- **OR3 Undamped driven.** x = x₀cos ω₀t + (v₀/ω₀)sin ω₀t + f·B(t),
  B = [t/(ω₀ + ω)]·sin((ω₀ + ω)t/2)·sinc((ω₀ − ω)t/2), equal to t sin(ω₀t)/(2ω₀) at ω = ω₀.
- **OR4 Free decay.** Successive maxima are T_d apart, with ratio e^{−γT_d} (exact).
- **OR5 Resonance.** Power P(ω) = (F₀²/m)·γω²/((ω₀² − ω²)² + 4γ²ω²) peaks at ω₀; its
  half-maximum points satisfy ω² ± 2γω − ω₀² = 0, so the width is exactly 2γ. Amplitude peak
  ω_r = √(ω₀² − 2γ²), A_max = f/(2γω_d), for ζ < 1/√2.
- **OR6 Energy.** E = ½mv² + ½kx², dE/dt = −bv² + F₀cos(ωt)·v; conserved when b = F₀ = 0.
  Steady state: mean power in = ½F₀ωA sin δ = ½bω²A² (identity).
- **OR7 Limits.** Continuity of x(t) across ζ = 1 and as b → 0, ω → ω₀ (b = 0) and F₀ → 0.
- **OR8 ODE residual.** The closed-form x, v satisfy the ODE and the initial conditions.

**Status: derived on paper; partly checked in scratch** (one machine, NumPy 2.5.4, SciPy
1.18.1; scripts in the session scratchpad, **not** repository tests): OR1-OR3 against a
DOP853 solve at rtol = 1e-13 on ten cases (under-, critically, nearly critically and
overdamped; driven at, below and away from resonance; b = 0 at and near resonance; b = 0.001
at resonance) agreed to ≤ 8.2e-12 of max|x|, except one overdamped case at 7e-11, traced to
the reference solve (D7); OR5's width was 2γ to 7.3e-13 rad/s (γ = 0.4 s⁻¹) and the amplitude
peak matched its formula to 9e-10 rad/s (the optimiser's tolerance); OR4's period and ratio
matched to 5.5e-15 and 1.2e-14 relative. OR6-OR8 are not yet checked.

## Seams (where tests attach; what each catches and misses)
1. **Exact solution** (`analytical.py`, pure; also 2.4's reference). Tests: OR1-OR8 against
   the 60-digit `decimal` branch formulas and an in-test integration; continuity across ζ = 1
   (1 ± 1e-8) and near ω₀ with b = 0; no overflow at γT = 1e5; the Q ≤ 1e4 cancellation bound
   measured at the limit. *Catches* formula, branch and rounding errors. *Misses* the solver.
2. **Numerical solve** (`numerical.py`, pure). Tests: agreement with seam 1 at tight
   tolerances in every regime; the scaled and SI states agree; the works are coded independently
   (a mutant with the wrong damping force, e.g. −b·v·|v|/V, fails the energy balance); maxima
   events. *Catches* ODE and scaling bugs. *Misses* the checks' wording and the API.
3. **Model run and checks** (`model.py`). Tests: checks pass on a grid of corners; a planted
   error fails them; nulls when undriven, undamped or overdamped; the guard refuses before any
   solve and names its number; threshold measurements recorded. *Catches* assembly, labelling
   and threshold bugs.
4. **API and registry.** Validation (NaN, ±Infinity, every bound and combined rule with its
   message, nothing moves), a corners test (never a 500, each refusal explained, time
   measured), registry rebuild, one tolerance rule per stored field, the appended golden run,
   replay and recompute, existing digests unchanged.
5. **Frontend.** Vitest for the lab (presets, nulls, resonance chart only when driven),
   `exportTables`, `compare`, `overlay`; Playwright: run each preset, pin a reference run, the
   two stored-fields cases. *Misses* scientific errors, which seams 1-3 own.

## Slices (test-first with `tdd`, one per autopilot tick, one commit each)
1. **Exact solution** (seam 1). Accept when: OR1-OR8 tests written first and passing; every
   regime agrees with the 60-digit reference to ≤ 1e-13 of X; pitfalls (i)-(iii) have a test
   each; the Q-limit bound is measured and recorded. Fresh-context review (scientific core).
2. **Numerical solve and run** (seams 2-3), plus `schemas.py`. Accept when: tests first; checks
   pass on a corner grid (≥ 3 methods × 4 tolerance pairs × all regimes × driven/free), with
   thresholds and N_max **set from measurement** and the numbers recorded for
   `SCIENTIFIC_VALIDATION.md`; the mutant fails; no existing test changes. Fresh-context
   review (scientific core, limits).
   **Acceptance block** (added 2026-11-09). Both test files are written first and must fail on
   the current code (`numerical.py` and `model.py` do not exist yet).
   - **Test files:** `backend/tests/physics/test_oscillator_numerical.py` (seam 2: agreement
     with `analytical.state` in every regime, scaled against SI states, maxima events against
     OR4, the wrong-damping mutant monkeypatched over `numerical.py`'s damping-force function
     as `test_quadratic_numerical.py` does); `backend/tests/physics/test_oscillator_model.py`
     (seam 3 and `schemas.py`: a parametrised `test_corner_grid*`, the planted error, nulls
     when undriven, undamped or overdamped, the guard refusing before any solve and naming its
     number, and the measurements behind the thresholds and N_max).
   - **Commands** (from `backend/`): `uv run pytest tests/physics/test_oscillator_numerical.py
     tests/physics/test_oscillator_model.py -q` (red before the build, green after);
     `uv run pytest tests/physics/test_oscillator_model.py -q --collect-only -k corner_grid`;
     `uv run ruff check . && uv run ruff format --check . && uv run mypy`; `uv run pytest -q`.
     From the root, before the slice's commit: `git diff --stat --diff-filter=MDR HEAD --
     backend/tests` and `python3 scripts/doc_index.py --check`.
   - **Checks (yes/no):** (1) The corner grid collects ≥ 96 cases, RK45, DOP853 and Radau ×
     (rtol, atol) = (1e-13, 1e-14), (1e-10, 1e-10), (1e-6, 1e-8), (1e-3, 1e-1) (tightest
     allowed, default, middle, loosest allowed) × the four `Regime` values × driven/free, plus
     the Risks corners (ω far below ω₀ and at 100·ω₀, tiny x₀ with v₀, Q = 1e4 and b = 0 at
     resonance, a run of N_max cycles), and every check passes on each? (2) The wrong-damping
     mutant fails the energy balance while the true code passes it? (3) The scaled and SI
     states agree to rounding (bound in ε, justified in the test), and at the tightest pair the
     solution matches seam 1 in every regime within the measured thresholds? (4) Every
     threshold and N_max is a named constant whose comment cites its measurement, and the same
     numbers are in `SCIENTIFIC_VALIDATION.md`'s oscillator section (read in the diff)?
     (5) ruff, format, mypy and the full `pytest -q` pass (golden digests included), and the
     `git diff` command prints nothing (no existing test file changed)? (6) A fresh-context
     review (opus, high; scientific core, limits) was run and its findings are fixed or
     recorded?
   - **Velocity scale (the author's decision, 2026-11-09): V = ω₀X**, as in D5 (η = v/(ω₀X))
     and D8 (energy normalised by kX² = m(ω₀X)²); it replaces the slice-1 note's
     max(ω₀, ω)·X, which could be up to 100× larger than the motion and hide errors. The grid
     records the worst max|v|/(ω₀X) as evidence, and the thresholds are measured with V = ω₀X.
   - **Thresholds from measurement:** start from D8's `1e4 × (rtol + atol) + 1e-9` (scaled),
     measure the worst value of each check on the grid, then set the threshold from it with
     the margin stated and justified; a cycles factor only if the measurement shows growth
     with cycles (Risks); never tuned until a test passes. N_max from the timed slowest
     allowed run against D6's ≤ 2 s. Recorded for `SCIENTIFIC_VALIDATION.md`: per check, the
     worst ratio and its corner; N_max and its time; the machine, NumPy and SciPy versions.
   - **Not done (worth doing from review):** a unit-invariance test (scale m, k, b, F₀ by λ)
     instead of the scaled-against-SI tautology; thresholds as D8 coefficients, with the
     loosest tolerance pair labelled uninformative where its threshold exceeds 1; the energy
     normalisation must match the chosen V; name the corner test IDs and keep the N_max and
     Radau corners tractable; N_max timing as a recorded measurement, not a timed assertion;
     each threshold must exceed `analytical.py`'s own reference floor; name the module-level
     damping function for the mutant and the planted-error test; `schemas.py` validation is
     tested in slice 3 (slice 2 needs mypy only); the plan's status updated per G4.
3. **API** (seam 4). Route module, `ModelEntry` (inputs, summary, tolerances with reasons,
   headline "x₀ 0.1 m, ζ 0.05 (underdamped), Q 10", rebuild), registry, union, appended golden
   run, corners test, `make api-types`. Accept when: `pytest` green, golden diff shows only the
   new entry, `/security-review` run (new inputs and limits) with findings addressed.
4. **Frontend** (seam 5). Page, presets, three charts, results, validation, nav, D15 wiring.
   Accept when: Vitest and the new Playwright cases pass; no existing frontend test changes.
5. **Docs** (D16), then `scripts/check.sh --e2e` and a fresh-context review of the whole PR.
   Accept when: Part 20 ≈ 250 lines with tags matching the files; ROADMAP 2.3 ✅; all checks
   green; the handoff rewritten.

## Risks
- **Thresholds and N_max are unmeasured** (D6, D8); the phase error of long runs may force a
  cycles factor into the thresholds, which slice 2 must justify, not guess.
- **The Q ≤ 1e4 gap**: a lightly damped oscillator (1e4 < Q < ∞) is refused while b = 0 is
  allowed; explained in the 422; reversal is the stable divided-difference form (D3).
- **The scale X** (D5) is a judgement; a corner where the motion is far below X would make the
  checks loose. Slice 2's grid must include drive far above and below ω₀ and tiny x₀ with v₀.
- **Step counts** make replay say "differs" on another CPU (2.2 B6); unchanged here.
- **IB syllabus details** for damping, resonance and Q are marked "verify" (`docs/IB_FOUNDATIONS.md`
  P5 says detailed lines are unverified); the guide must not claim IB coverage it has not checked.
- **Overlap with Track A P5**: both cover SHM of a spring; P5 stays planned as an IB precursor.
- **Unverified:** OR6-OR8 numerically; run time at N_max; the 30 s proxy limit at the slowest
  allowed run.

## Out of scope (for the author)
- A **simulated** resonance curve (one run per drive frequency): roadmap 2.5, which could
  offer "sweep `drive_angular_frequency`, report the late-time amplitude" against D9's formula.
- Fixed-step, symplectic Euler and Verlet on the oscillator, and long-run energy drift: 2.4.
- The nonlinear pendulum (Ext), animation (2.6), phase portraits, a drive-phase input, coupled
  oscillators.

## Genuine stops found
None. Checked: no new dependency (NumPy, SciPy and stdlib `decimal`, all in use); no change to
the roadmap's scope or order (the exact resonance curve is the capability map's Core item for
oscillators and needs no solves; the simulated one stays with 2.5); no migration (a new model,
endpoint, registry entry and union member are additive; the golden test guards existing
digests); no guard-rail file touched; every claim has an independent reference (OR1-OR8 against
`decimal` and in-test integrations) or is labelled approximate (Q from energy per cycle).
**Flagged, not blocking:** (1) the exact resonance curve is included (D9), reversible; (2) the
guide invites the author to write the oscillator's symplectic methods himself: 2.3 leaves them
to 2.4 so that stays open; if the author wants to write part of 2.3 itself, say so before slice 1.
