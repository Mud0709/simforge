# Scientific validation

This document explains how SimForge establishes that its numbers are right, and how far that
evidence goes. It is a living document: every new model adds a section.

## Principles

1. **Independent references.** A test's expected value must come from somewhere other than the
   code under test: a textbook formula, a physical limit or invariant, a higher-precision
   evaluation, or a second, independent method.
2. **Name the approximation.** Results are labelled *exact*, *exact equation solved
   numerically to tolerance X*, or *numerical approximation*. An approximation is never
   presented as an exact solution.
3. **Tolerances are justified.** Each tolerance is derived from floating-point limits
   (`ε ≈ 2.2e-16`), the solver tolerance, or the conditioning of the problem. It is not
   chosen just because it makes the test pass.
4. **Report, don't claim.** Accuracy figures below are *observed* values from a specific
   run, with versions. They are not guarantees for other inputs.
5. **Validation is not verification of the physics.** The tests show that the code solves its
   stated equations correctly. They cannot show that the equations describe reality. Model
   assumptions are documented separately and returned with every result.

---

## `physics.projectile` v1.0.0: projectile motion with linear drag

### Model

A point mass `m` under uniform gravity `g` with linear drag `F = −b v`. With `k = b/m`:

```
dvx/dt = −k vx          dvy/dt = −g − k vy
```

Units are SI throughout: m, s, kg, kg/s, m/s². Launch angle is in degrees at the API
boundary and in radians internally. Assumptions are listed in
`backend/src/simforge/physics/projectile/model.py` and are returned in every API response.

### Two independent solutions

| | Analytical reference | Numerical solution |
|---|---|---|
| Trajectory | Exact closed form, `x = vx0·t·ψ(kt)`, `y = h + vy0·t·ψ(kt) − g t² φ(kt)` | SciPy `solve_ivp` (RK45, DOP853 or Radau) on the ODEs |
| Landing time | Root of the exact `y(t)` by Brent's method, `rtol = 4ε`. Cross-checked against the Lambert-W closed form | Event detection on `y = 0` |
| Apex | Closed form `t = ln(1 + vy0/v_t)/k` | Event detection on `vy = 0` |
| Knows about the other? | No | Only uses `2 × T_exact` as a safety cap on integration time |

### Numerical-analysis issue handled: catastrophic cancellation

The textbook form `y = τ(vy0 + v_t)(1 − e^{−t/τ}) − v_t·t` subtracts two numbers of size
`v_t·t` (≈1e10 m when `b/m = 1e-9`) to produce a result of ≈10 m. The rounding error
(≈1e-6 m) then becomes a relative error of ≈1e-7. SimForge instead uses the
auxiliary functions

```
ψ(u) = (1 − e^{−u})/u        φ(u) = (e^{−u} − 1 + u)/u²
```

evaluated with `expm1` for `u ≥ 0.1` and a 12-term Taylor series for `u < 0.1`. This form is
accurate to ~1e-15 relative for all `u ≥ 0`, and it reduces *exactly* to the vacuum formulas
at `b = 0` (`ψ(0) = 1`, `φ(0) = ½`). That means a single code path, with no special case.
`test_stable_form_avoids_catastrophic_cancellation` demonstrates both the failure and the fix
against a 50-digit `decimal` reference.

### What is tested

All tests are in `backend/tests/physics/`.

| Check | Reference | Tolerance | Why that tolerance |
|---|---|---|---|
| `ψ`, `φ` at 11 points from 1e-12 to 100, including either side of the series switch | 50-digit `decimal` | rel 1e-15 | A few ε |
| Vacuum range `v²sin2θ/g`, flight time `2v sinθ/g`, height `v²sin²θ/2g` (5 angles) | Textbook | rel 1e-13 to 1e-14 | Several ε, plus one root-find |
| Vacuum launch from height | Quadratic formula | rel 1e-14 | — |
| Complementary angles give equal range; 45° maximises range | Symmetry | rel 1e-13 | — |
| Closed form satisfies the ODEs | Central finite differences | rel 1e-8 | FD truncation (h²) and rounding (ε/h) |
| Landing time matches the Lambert-W closed form (4 cases) | Independent formula | rel 1e-12 | Lambert W is ill-conditioned near its branch point |
| Weak drag (`b = 1e-12`) → vacuum | Limit | rel 1e-10 | Physical difference is O(k·T) |
| Range decreases monotonically with `b` | Physics | strict | — |
| Long fall reaches terminal velocity `g/k` | Limit (k·T > 500) | rel 1e-12 | — |
| All 3 solvers × 3 drag values agree with the exact solution | Exact solution | position < 1e-7 m, metrics rel < 1e-9, energy < 1e-8 | Global error ≈ a modest multiple of `rtol = 1e-10` for this smooth problem |
| Error falls as `rtol` tightens (1e-4 → 1e-10) | Convergence | >1e3 × reduction | Error should track tolerance |
| Vacuum conserves mechanical energy | Invariant | 1e-12 | — |
| Drag work is non-negative and monotonic | Second law | strict | — |
| Stiff inputs sent to an explicit solver are refused | Guard | — | `k·T > 1e4` would need ≥ ~1e4 stability-limited steps |

API tests (`backend/tests/api/`) check input validation, including `NaN` and `±Infinity`,
which Python's JSON parser accepts. They also check that errors are reported in valid JSON,
that identical inputs give bit-identical results and identical input hashes, and that saved
runs persist.

### Observed accuracy

Measured on 2026-10-14 with Python 3.12.3, NumPy 2.5.4 and SciPy 1.18.1 on linux-x86_64.
Inputs: `v0 = 20 m/s`, `θ = 45°`, `h = 3 m`, `m = 1 kg`, `g = 9.80665 m/s²`, `rtol = atol = 1e-10`.

| b (kg/s) | Method | Rel. error, flight time | Max position error (m) | Max energy residual (×E₀) | Steps |
|---|---|---|---|---|---|
| 0 | RK45 | 0 | 3.6e-15 | 1.2e-16 | 5 |
| 0 | DOP853 | 1.9e-15 | 1.1e-13 | 2.1e-15 | 4 |
| 0 | Radau | 2.9e-16 | 3.2e-14 | 1.2e-16 | 5 |
| 0.1 | RK45 | 2.2e-12 | 9.8e-11 | 2.5e-11 | 28 |
| 0.1 | DOP853 | 5.0e-13 | 2.2e-11 | 1.3e-12 | 5 |
| 0.1 | Radau | 2.0e-13 | 9.0e-12 | 2.3e-12 | 183 |
| 5 | RK45 | 2.6e-13 | 4.0e-11 | 2.2e-12 | 179 |
| 5 | DOP853 | 7.5e-14 | 3.3e-12 | 1.5e-12 | 34 |
| 5 | Radau | 3.2e-13 | 2.6e-12 | 2.8e-15 | 699 |

How to read this table:

- **Vacuum results are not a fair test of a solver.** The vacuum trajectory is a quadratic
  polynomial in `t`, and Runge-Kutta methods of order ≥ 2 integrate such solutions exactly,
  apart from rounding. The near-ε errors in the `b = 0` rows therefore say little about solver
  quality. The drag rows, whose solution contains `e^{−kt}`, are the meaningful test.
- The high-order method (DOP853) takes far fewer steps than RK45 for the same tolerance.
- Radau, an implicit method designed for stiff problems, does much more work on this
  non-stiff problem. This is expected; it is included for strongly damped cases.

To reproduce, run `cd backend && uv run pytest tests/physics -v`. Any single run's figures
also appear in its API response under `comparison`.

### Known limitations

- **Linear drag only.** Real balls experience drag closer to `F ∝ v²`, which has no
  closed-form 2-D solution. That model will be validated against limits, invariants and
  convergence studies instead (see ROADMAP).
- **The reported error does not measure interpolation error.** Error metrics are evaluated at
  the solver's accepted step nodes. Plotted curves come from the dense-output interpolant,
  which adds its own (smaller-order) error that is not reported.
- **The integration cap depends on the exact solution.** The numerical run uses `2 × T_exact`
  as its integration cap. The answer is found independently, but a future model without
  an exact solution will need a different bound.
- **Bounds are pragmatic.** Input bounds keep runs fast and finite. They do not mark the
  physical validity range, which depends on the assumptions.
- **Results are bit-identical across repeated runs on the same machine** (this is tested).
  They are not guaranteed bit-identical across CPUs or library versions, which is why
  versions are recorded with every run.

---

## `physics.projectile.integrators` v1.0.0: fixed-step integrator convergence study

### Purpose

The linear-drag projectile has an exact solution, so the error of any integrator applied to
it can be measured exactly. This study implements three fixed-step methods **from scratch**
(no SciPy integrators) and measures how their errors shrink as the time step `h` is reduced.

Engine code: `backend/src/simforge/numerics/fixed_step.py` and `convergence.py` (generic) and
`backend/src/simforge/physics/projectile/integrator_study.py` (problem-specific).

### Equations

State `s = (x, y, vx, vy)`, `k = b/m`:

```
x' = vx     y' = vy     vx' = −k vx     vy' = −g − k vy
```

| Method | Update | Theoretical global order |
|---|---|---|
| Forward Euler | `s_{n+1} = s_n + h f(s_n)` | 1 |
| Classical RK4 | `s_{n+1} = s_n + h/6 (k1 + 2k2 + 2k3 + k4)` | 4 |
| Velocity Verlet, implicit drag | `r_{n+1} = r_n + h v_n + h²/2 a_n`;  `v_{n+1} = [(1 − kh/2) v_n − g h ŷ] / (1 + kh/2)` | 2 |

**Why this form of Verlet?** Standard velocity Verlet assumes the acceleration depends only on
position. Here `a = −g ŷ − k v` depends on velocity, so its velocity update
`v_{n+1} = v_n + h/2 (a_n + a_{n+1})` is implicit. Because drag is linear, that implicit
equation is solved *exactly* (formula above). The result is the trapezoidal rule for velocity,
which is second order and A-stable, plus a second-order Taylor step for position.

Verlet's usual advantages, symplecticity and good long-term energy behaviour, apply to
conservative Hamiltonian systems. This system is dissipative, so **no such claim is made**.
Verlet is included as a second-order method whose stability differs sharply from the two
explicit methods. Explicit "predicted-velocity" Verlet variants are not used, because they are
ad hoc and their order depends on the predictor.

### Linear stability

The Jacobian has eigenvalue 0 for position and `−k` for velocity. One step multiplies a
velocity perturbation by the method's stability function `R(z)` at `z = −kh`:

| Method | `R(z)` | Stable when | Behaviour beyond the limit |
|---|---|---|---|
| Euler | `1 + z` | `kh ≤ 2` | grows with alternating sign (`R < −1`) |
| RK4 | `1 + z + z²/2 + z³/6 + z⁴/24` | `kh ≤ 2.785293563…` | grows **without** alternating sign (`R > 1`) |
| Verlet (this form) | `(1 + z/2)/(1 − z/2)` | every `kh > 0` | — (but `R → −1` as `kh → ∞`: decay becomes slow and oscillatory) |

The RK4 limit is computed numerically as the nonzero real root of `R(z) = 1`, not hard-coded.
It is tested against the published value (Hairer & Wanner, *Solving ODEs II*, §IV.2).
An earlier draft of this work assumed the boundary was at `R = −1`, as it is for Euler. The
computation refused to find a root there, which is how the mistake was caught.

### Error metrics

- **Fixed horizon.** Every run integrates over `[0, T]`, where `T` is the exact flight time,
  using `N = ⌈T/dt⌉` equal steps of `h = T/N ≤ dt`. Convergence is fitted against `h`, not
  the requested `dt`. Landing is *not* detected: locating it between nodes would add an
  interpolation error (typically O(h²)) that could mask RK4's fourth order.
- **Max position error** = `max_n |r_n − r(t_n)|` (m), and **max velocity error** =
  `max_n |v_n − v(t_n)|` (m/s), over all nodes. Errors at `t = T` are also reported.
- **Reference.** The existing exact solution, evaluated in float64 with relative error about
  1e-15. That is far below every round-off floor below.

### A conserved linear invariant (and why it matters for the evidence)

Integrating `v' = −kv − gŷ` gives `I = v + k r + g t ŷ = constant` along the exact solution.
Every Runge-Kutta method, Euler and RK4 included, conserves linear invariants exactly. Their
errors therefore satisfy `δv_n = −k δr_n` at every node, so **velocity error = k × position
error** for Euler and RK4. This was first noticed as a suspicious coincidence in the data,
then explained by this theorem and tested to 1e-13. Consequently their fitted velocity orders
are *not independent evidence*. The position update of Verlet does not preserve `I`, so its
velocity order is an independent result.

### Fit-range rule (fixed before inspecting results)

A run contributes to the least-squares fit of `log10(error)` against `log10(h)` only if all
of these hold:

1. **Linearly stable:** `|R(−kh)| < 1`, and the run did not diverge.
2. **Asymptotic regime:** `kh ≤ 0.2` and `h ≤ T/20`. The leading error term dominates only
   when both expansion parameters are small. These thresholds are conventional, conservative
   choices; they were not tuned.
3. **Above round-off:** `error > 100 · N · ε · scale`, where `ε = 2.2e-16` and `scale` is the
   maximum of `|r|` (or `|v|`) over the exact solution. Accumulated rounding error grows at
   most about linearly in `N`; the factor 100 is a safety margin.

An order is reported only if **at least 3** distinct step sizes qualify. Otherwise the fit is
null and the response says why. Local orders `log(e₁/e₂)/log(h₁/h₂)` are reported for every
consecutive pair, so you can see whether the errors have actually reached the asymptotic
regime. The convergence plot draws a line of the *theoretical* slope from the finest fitted
point. It is shifted down by ×0.2 for visibility, and it is a guide, not a fit. Drawing it is
justified because the solution is infinitely differentiable, so the theoretical orders apply.

The round-off criterion is conservative. For example, RK4 at `h = 0.0031 s` (case A) has
error 8.1e-12 m against a floor of 1.9e-10 m and is excluded, even though its local order
(4.003) is still clean. A tighter floor would add points but would rest on a less defensible
bound.

### Tests

Model-independent (`backend/tests/numerics/`):

| Check | Reference |
|---|---|
| One step on `y' = λy` equals `R(λh)·y` (Euler, RK4; 5 values of z, including unstable ones) | Stability functions, rel 1e-15 |
| RK4 is exact for `y' = 4t³ − t` | Simpson's rule exactness for cubics |
| Orders 1 and 4 on `y' = −y` over 8 step sizes (errors > 1e-13 only) | `e^{−t}`, tolerance ±0.05 |
| Divergence is detected and stops early with finite values | `|R| = 9` |
| Fitting: exact power law recovered; fewer than 3 points, duplicates or zero errors refused; poor linearity shows in R² | Synthetic data |

Projectile study (`backend/tests/physics/test_projectile_integrators.py`):

| Check | Reference / tolerance |
|---|---|
| `vx_n = vx₀ R(−kh)ⁿ` for all 3 methods at kh ∈ {0.05, 0.5, 1.9, 2.5, 3, 10} | Exact discrete solution, rel 1e-12. Tests the code inside and beyond its stability limits |
| Euler at kh = 1.9 decays, at kh = 2.1 grows with alternating sign; RK4 at kh = 2.9 grows with constant sign; Verlet bounded at kh = 1000 | Stability theory |
| Stability classification at, below and above each limit | Theory |
| Fitted order within ±0.1 of theory, R² > 0.999, every in-fit local order within ±0.15, for 3 methods × 3 parameter sets | Theory, ≥ 3 points (≥ 5 in the default case) |
| Verlet's velocity order ≈ 2 (independent evidence) | ±0.1 |
| Linear invariant conserved by Euler/RK4 (1e-13); violated by Verlet | Theorem above |
| Round-off floor excludes the finest RK4 points; too few points ⇒ no order claimed | Fit rule |
| Divergent runs report null errors (strict JSON); unstable-but-finite runs are flagged and excluded | — |
| `dt > T` ⇒ one step; `⌈T/dt⌉` is robust to rounding noise; `h ≤ dt`; `N·h = T` | — |
| Vacuum (`b = 0`) rejected; results deterministic | — |

API tests (`backend/tests/api/test_integrators_api.py`) cover validation (zero drag, ≤ 0,
non-finite or duplicate steps, list length, unknown or duplicate methods, extra fields), the
step-count limits, persistence, and that `/simulate` is unaffected.

### Observed results

Measured on 2026-10-14 with Python 3.12.3, NumPy 2.5.4 and SciPy 1.18.1, using the step sizes
`dt = 0.2 × 2⁻ⁱ s`, i = 0…7 (0.2 s down to 0.0015625 s), and `g = 9.80665 m/s²`.

| Case | Method | Fitted order (position) | Points | Fit range h (s) | R² | Local orders inside the fit (coarse → fine) |
|---|---|---|---|---|---|---|
| A: v₀ = 20, 45°, h₀ = 0, m = 1, b = 1 (k = 1 s⁻¹, T = 2.161 s) | Euler | 1.009 | 7 | 0.00156–0.0982 | 0.999976 | 1.031 → 1.001 |
| | RK4 | 4.027 | 5 | 0.00624–0.0982 | 0.999994 | 4.059 → 4.008 |
| | Verlet | 2.000 | 7 | 0.00156–0.0982 | 1.000000 | 2.000 (all) |
| B: v₀ = 20, 30°, h₀ = 10, m = 2, b = 0.5 (k = 0.25, T = 2.752) | Euler | 1.003 | 7 | 0.00156–0.0983 | 0.999998 | 1.009 → 1.000 |
| | RK4 | 4.011 | **3** | 0.0248–0.0983 | 1.000000 | 4.015, 4.007 |
| | Verlet | 2.000 | 7 | 0.00156–0.0983 | 1.000000 | 2.000 (all) |
| C: v₀ = 15, 70°, h₀ = 2, m = 1, b = 3 (k = 3, T = 2.381) | Euler | 1.016 | 6 | 0.00156–0.0496 | 0.999943 | 1.045 → 1.003 |
| | RK4 | 4.040 | 5 | 0.00312–0.0496 | 0.999985 | 4.089 → 4.011 |
| | Verlet | 2.000 | 6 | 0.00156–0.0496 | 1.000000 | 2.000 (all) |

How to read this table:

- Fitted orders sit slightly *above* theory, and the local orders fall monotonically towards
  it. That is the signature of higher-order error terms that are still decaying at the
  coarser steps, not of a wrong method. The finest local orders are within 0.011 of theory
  in every case.
- **Case B's RK4 fit has only 3 points**, the documented minimum. With weak drag
  (k = 0.25 s⁻¹) the non-polynomial part of the solution is small, so RK4's error falls below
  the round-off floor sooner. The order is reported, but it rests on less evidence than the
  others.
- **Verlet's R² of 1.000000** reflects errors that are almost exactly proportional to h² over
  this range. That is expected for a second-order method on a smooth, linear problem.

To reproduce: `cd backend && uv run pytest tests/physics/test_projectile_integrators.py -v`,
or run the study from the UI (Physics Lab → Integrators).

### Known limitations

- **One problem only.** Convergence is demonstrated on a single, linear ODE system (plus the
  scalar test equation). Nonlinear problems, such as quadratic drag, can behave differently.
- **Fixed horizon, not landing.** The study does not measure errors in the landing time or
  range for fixed-step methods. Those would need event location, whose interpolation error
  would itself need analysis.
- **Velocity orders for Euler/RK4 are not independent**, because of the linear invariant.
- **The thresholds are heuristics.** `kh ≤ 0.2`, `h ≤ T/20` and the ×100 round-off margin are
  conventional choices, stated in advance. Different reasonable thresholds would include
  different points.
- **Performance.** The integrators are plain Python loops (about 17 µs per RK4 step). Requests
  are therefore capped at 50,000 steps per run and 150,000 per study.
- **Not a proof.** The fits are empirical evidence consistent with theory on the cases tested.
  They are not a proof of order and say nothing about other problems.

---

## `physics.projectile.angle_sweep` v1.0.0: range against launch angle

### What it computes
For fixed speed, height, mass, drag and gravity, the exact linear-drag range `R(θ)` is computed
at evenly spaced angles from 0° to 90°. The angle that maximises the range is then found by
refining the best grid point with a bounded Brent search (`xatol = 1e-7°`) on the
neighbouring grid interval. Engine: `backend/src/simforge/physics/projectile/angle_sweep.py`.

The vacuum optimum has a closed form, reported alongside the drag result for comparison:
`tan θ* = v₀ / √(v₀² + 2gh)` and `R* = (v₀/g)·√(v₀² + 2gh)`, which gives 45° and `v₀²/g`
when `h = 0`.

### Precision
The range curve is flat at its peak: `R(θ* + δ) ≈ R* − ½|R''|δ²`. The maximum range is
therefore known to near machine precision, while the best angle is only well-defined to
about `√ε` in relative terms. Tests check the range to `1e-12` relative and the angle to
`1e-5°` against the closed form.

### Tests (`backend/tests/physics/test_angle_sweep.py`, `tests/api/test_angle_sweep_api.py`)
| Check | Reference |
|---|---|
| Vacuum from the ground: best angle 45°, `R* = v²/g` | Textbook |
| Vacuum from h = 5, 10, 50, 200 m: angle and range | Closed form above |
| Complementary angles give equal vacuum range | Symmetry |
| With drag: best angle < 45° and decreasing as b rises (b = 0.01…3 kg/s) | Physical property |
| `b = 1e-6` gives 45° to within 1e-3° | Limit |
| Exactly one peak on a 0.25° grid, for 5 drag values | Assumption behind the refinement |
| Refined optimum ≥ every grid point, and ±0.001° does no better | Definition of a maximum |
| Sweep values equal `analytical.state` at the landing time | Consistency |
| Drag never increases the maximum range | Physics |
| API: 45° and `v²/g` end to end; launch angle ignored in results and hash; validation | Contract |

### Observed (2026-10-15)
With `v₀ = 20 m/s`, `h = 0` and `m = 1 kg`, the best angle was 44.73°, 42.48°, 35.46°,
30.08° and 20.07° for `b = 0.01, 0.1, 0.5, 1, 3 kg/s`.

### Limitations
- Linear drag only. Quadratic drag (ROADMAP Milestone 1.1) is expected to behave differently.
- The single-peak property is checked on the tested cases, not proven in general. If a curve
  ever had two peaks, the refinement could miss the global maximum by up to one grid step.
- Only the launch angle is swept. Other parameters are fixed.
