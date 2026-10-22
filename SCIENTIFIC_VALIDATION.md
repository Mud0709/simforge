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
5. **Validation is not verification of the physics (or the economics).** The tests show that
   the code solves its stated equations correctly. They cannot show that the equations
   describe reality. Model assumptions are documented separately and returned with every
   result.
6. **Proofs, tests and evidence are different things.** A *mathematical guarantee* is proved
   on paper. A *test* checks that the implementation behaves as the proof says. An
   *empirical bound* (e.g. on rounding error) held on a stated grid of inputs and is not a
   theorem. Each section says which is which.

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
accurate to within 2e-15 relative (an empirical bound: the worst error measured on dense
grids over `1e-12 ≤ u ≤ 100` was 1.6e-15), and it reduces *exactly* to the vacuum formulas
at `b = 0` (`ψ(0) = 1`, `φ(0) = ½`). That means a single code path, with no special case.
`test_stable_form_avoids_catastrophic_cancellation` demonstrates both the failure and the fix
against a 50-digit `decimal` reference.

### What is tested

All tests are in `backend/tests/physics/`.

| Check | Reference | Tolerance | Why that tolerance |
|---|---|---|---|
| `ψ`, `φ` on 2002 points from 1e-12 to 100, densely around the series switch at 0.1 | 50-digit `decimal` | rel 4e-16 (`ψ`), 2e-15 (`φ`) | Empirical: worst measured 2.2e-16 and 1.6e-15 |
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
| Shallow launches from the ground (0.001° to 1°, all 3 solvers) land at the exact time | Exact solution | rel 1e-6 | Catches a landing reported at t = 0 (a 100 % error); far above solver error |
| A vertical launch has range exactly 0 and a null relative range error | Exact (`v_x = 0`) | exact | — |

**Input limits** (`tests/api/test_physics_limits.py`): mass ≥ 1e-6 kg, initial speed
≥ 1e-3 m/s and drag rate `k = b/m ≤ 1e4 s⁻¹` (drag acting over at least 0.1 ms); integrator
steps `dt ≥ 1e-9 s`. Below these the linear-drag model is not physically meaningful and the
arithmetic could overflow or underflow (before the limits, `m = 1e-305, b = 1e6` crashed with a
division by zero). The test runs every corner of the allowed space through the API: each one
either runs (finite, and agreeing with the exact solution to rel 1e-5 wherever the motion is
much larger than the solver's 1e-10 m absolute tolerance) or is refused with a 422 that
explains why. None returns a 500.

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
- **Interpolation error is mixed in, not separated out.** Error metrics are evaluated at the
  solver's accepted step nodes, but the last node (the landing) and the event-located apex
  come from the dense-output interpolant, so they include interpolation error. Plotted curves
  also come from the interpolant. Interpolation error is not reported separately.
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
  using `N = ⌈T/dt⌉` equal steps of `h = T/N ≤ dt` (up to a relative 1e-12 that absorbs
  rounding noise in `T/dt`). Convergence is fitted against `h`, not
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
| `dt > T` ⇒ one step; `⌈T/dt⌉` is robust to rounding noise; `h ≤ dt (1 + 1e-12)`; `N·h = T` | — |
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
neighbouring grid interval. SciPy's bounded Brent stops within `√ε·|θ| + xatol/3`, about
7e-7° near 45°, so the angle is known to roughly 1e-6° (measured: up to 6.9e-7° from 45° on
grids that do not contain 45°). Engine: `backend/src/simforge/physics/projectile/angle_sweep.py`.

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
| Vacuum from the ground: best angle 45° (to 1e-6°, on a grid that does not contain 45°), `R* = v²/g` | Textbook |
| Vacuum from h = 5, 10, 50, 200 m: angle and range | Closed form above |
| Complementary angles give equal vacuum range | Symmetry |
| With drag: best angle < 45° and decreasing as b rises (b = 0.01…3 kg/s) | Physical property |
| `b = 1e-6` gives 45° to within 1e-3° | Limit |
| Exactly one peak on a 0.25° grid, for 5 drag values | Assumption behind the refinement |
| A dense scan (1e-6° steps, ±1e-4°) finds no longer range than the reported one, beyond 8 ulps; mutation-checked to catch a reported angle 1e-5° off | Independent search method |
| Vacuum flight time and maximum height at 3 angles and heights | Textbook formulas |
| The 90° point has range exactly 0 | Exact |
| Drag never increases the maximum range | Physics |
| API: 45° and `v²/g` end to end; launch angle ignored in results and hash (including 0° from the ground); validation | Contract |

### Observed (2026-10-15)
With `v₀ = 20 m/s`, `h = 0` and `m = 1 kg`, the best angle was 44.73°, 42.48°, 35.46°,
30.08° and 20.07° for `b = 0.01, 0.1, 0.5, 1, 3 kg/s`.

### Limitations
- Linear drag only. Quadratic drag (ROADMAP Phase 2) is expected to behave differently.
- The single-peak property is checked on the tested cases, not proven in general. If a curve
  ever had two peaks, the refinement could miss the global maximum by up to one grid step.
- Only the launch angle is swept. Other parameters are fixed.

---

## `economy.solow` v1.0.0: Solow growth model in discrete time

Engine: `backend/src/simforge/economy/solow/simulation.py` (pure). Orchestration and per-run
checks: `model.py`. Tests: `backend/tests/economy/test_solow.py`,
`backend/tests/api/test_solow_api.py`.

### Model
Production `Y_t = K_t^α (A_t L_t)^(1−α)`, with `L_{t+1} = (1+n)L_t` and `A_{t+1} = (1+g)A_t`.
A share `s_t` of year-t output is saved and becomes capital at the start of year t+1;
depreciation applies to `K_t`: `K_{t+1} = s_t Y_t + (1−δ)K_t`. Dividing by
`A_{t+1}L_{t+1} = D·A_tL_t`, with `D = (1+n)(1+g)`, gives the recurrence for capital per
effective worker `k = K/(AL)`:

`k_{t+1} = f(k_t) = [s_t k_t^α + (1−δ)k_t] / D`

Output per effective worker is `y = k^α`, consumption `c = (1−s)y`, investment `i = sy`.
Output per actual worker is `Y/L = A_t·y_t`, reported as an index with year 0 = 100.

**Policy experiment.** `s_t = s₀` for `t < T_c` and `s₁` for `t ≥ T_c`, with
`0 ≤ T_c < H`. Because `s_t` is applied to year-t output, the first capital stock affected
is `k_{T_c+1}`; consumption changes already at `t = T_c`.

**Accepted inputs.** `α ∈ [0.05, 0.95]`, `s ∈ [0.01, 0.99]`, `δ ∈ [0, 1]`,
`n ∈ [−0.05, 0.10]`, `g ∈ [0, 0.10]`, `k₀/k*(s₀) ∈ [0.01, 10]`, `H ∈ [1, 500]` years, and
`λ = n + g + ng + δ ≥ 10⁻³` (with a 10⁻¹² relative allowance so inputs whose exact sum equals
the bound are not rejected by rounding). Under these bounds `k*` lies between about `10⁻⁴²` and
`10⁶⁰`, so nothing can overflow or underflow; the model still checks every path is finite.

### Mathematical guarantees (proved; the tests check the implementation obeys them)
Let `λ = D − (1−δ) = n + g + ng + δ > 0` and `φ(k) = f(k)/k = [s k^(α−1) + 1 − δ]/D`.

1. **f is strictly increasing on k > 0**: `f′(k) = [αs k^(α−1) + 1 − δ]/D > 0`.
2. **Unique positive steady state.** φ is continuous and strictly decreasing (α − 1 < 0),
   tends to ∞ as k → 0 and to `(1−δ)/D < 1` as k → ∞ (equivalent to λ > 0). So φ = 1 at
   exactly one point, `k* = (s/λ)^(1/(1−α))`, with `f(k) > k` below it and `f(k) < k` above.
3. **Side-preserving monotone convergence.** If `0 < k < k*`, then `k < f(k) < f(k*) = k*`
   (by 2 and 1). The path rises strictly and is bounded by k*, so it converges; by continuity
   the limit is a positive fixed point, which by 2 is k*. Symmetrically from above.
4. **Monotone growth of output per worker.**
   `G_t = (Y/L)_{t+1}/(Y/L)_t − 1 = (1+g)·φ(k_t)^α − 1`. Below k*, `k_t` rises (3) and φ falls
   (2), so `G_t` falls strictly, stays above g (since φ > 1), and tends to g. Above k*, it
   rises strictly towards g from below.
5. **Policy stretches.** 3 and 4 apply separately to each constant-savings stretch,
   `t = 0…T_c` with `k*(s₀)` and `t = T_c…H` with `k*(s₁)`. The side of `k*(s₁)` on which the
   second stretch starts depends on `k_{T_c}`, **not** on whether s rose or fell: both
   sides occur for both directions. The first stretch is finite, so only "moves strictly
   towards k*(s₀)" is claimed there, not convergence.
6. **Convergence factor.** `ρ = f′(k*) = (αλ + 1 − δ)/D ∈ (0, 1)`, and
   `1 − ρ = (1−α)λ/D`. ρ does not depend on s.
7. **Golden rule.** Steady-state consumption per effective worker is
   `c*(s) = (1−s)k*(s)^α = k*^α − λk*` (using `s k*^α = λ k*`). This is strictly concave in
   k* with maximum at `k_gold = (α/λ)^(1/(1−α))`, and `k*(s)` is strictly increasing, so the
   unique maximising savings rate is **`s_gold = α`**, for every n, g, δ. Since `A_t` does not
   depend on s, the same s maximises steady-state consumption per actual worker.
8. **Continuous-time link.** Scaling all four rates by ε (one model year represents a period
   ε) gives `k*_ε = (ŝ/(λ̂ + ε n̂ĝ))^(1/(1−α))`, which tends to the continuous-time
   `(ŝ/λ̂)^(1/(1−α))` with first-order error; the two agree exactly when `n̂ĝ = 0`. In
   continuous time `z = k^(1−α)` obeys `dz/dτ = (1−α)(ŝ − λ̂z)`, so
   `z(τ) = z* + (z₀ − z*)e^(−βτ)` with `z* = ŝ/λ̂` (the capital-output ratio, in years) and
   `β = (1−α)λ̂` (per year), and `(1−ρ)/ε → β`.

**Approximation, labelled as such:** the half-life `ln 0.5 / ln ρ` comes from linearising f
at k*, so it describes small deviations only.

### Numerical-analysis issue handled: cancellation in λ
`λ = (1+n)(1+g) − (1−δ)` subtracts two numbers close to 1 when the rates are small. On the
grid below this lost up to about 900 units of `u·(1/(1−α)+2)` in `k*` (516 u in λ itself for
`n = 0, g = 0.001, δ = 0.0011`). SimForge computes `λ = n + g + ng + δ` directly (worst error
on the grid: 1.39 u) and `1 − ρ = (1−α)λ/D` directly; the half-life uses
`log1p(−(1−ρ))`. A test documents the cancellation so the direct form is not "simplified"
back.

### Empirical evidence (held on the grid; not theorems)
Grid: every combination of `α ∈ {0.05, 0.3, 0.6, 0.9, 0.95}`, `s ∈ {0.01, 0.2, 0.5, 0.99}`,
`δ ∈ {0, 0.0011, 0.05, 1}`, `n ∈ {−0.05, 0, 0.1}`, `g ∈ {0, 0.001, 0.05, 0.1}` with
`λ ≥ 10⁻³`: 780 cases, 195 distinct economies. `u = 2⁻⁵³ ≈ 1.1e-16`.

| Quantity | Bound tested | Worst observed |
|---|---|---|
| λ relative error vs exact rational | 4 u | 1.39 u |
| `k*` relative error vs 60-digit `Decimal` | 8 u·(1/(1−α)+2) | 3.21 u·(1/(1−α)+2) |
| Steady-state residual `|f(k*)−k*|/k*` | 1e-13 | 5.0 u (5.6e-16) |
| `max_t |k_t/k* − 1|` starting at k*, 500 years | 64 u/(1−ρ) | 4.75 u/(1−ρ) |

The `64 u/(1−ρ)` form comes from a heuristic: rounding of a few u per step, damped by a
factor ρ per step, accumulates to at most about `u/(1−ρ)`. It is **a hypothesis that held
with a wide margin on this grid**, not a proven bound. In one slow case
(`1/(1−ρ) ≈ 9 100`), a path run for 545 455 years ended within 1.1e-12 of k*, inside the bound.

Policy-change evidence: 13 248 two-stretch paths (4 α × 3 δ × 3 n × 3 g × 12 ordered
(s₀, s₁) pairs × 4 starting ratios × 3 policy years) obeyed guarantees 3-5 in both stretches,
with every (direction, side) combination occurring. The test suite runs a smaller version of
this (3 economies) that also asserts all combinations occur.

### What is tested
| Check | Kind |
|---|---|
| `k*` matches the formula and is a fixed point; ρ equals a finite-difference `f′(k*)`; `ρ^half-life = 0.5` | Exact reference |
| λ accurate to 4 u; subtraction form demonstrably worse | Exact reference / regression guard |
| Strictly monotone, side-preserving paths and strictly monotone `G_t` (195 economies × 3 s × 4 starts) | Guarantees 3-4 |
| Paths reach k* (e^−60 of the gap removed) for fast, slow and extreme cases | Guarantee 3 |
| Two-stretch policy paths, side read from data, all combinations present | Guarantee 5 |
| `(k_{t+1}−k*)/(k_t−k*) → ρ` with error proportional to the deviation | Guarantee 6 / Taylor |
| Golden rule: `k*` by **Brent root-finding** (not the closed form), then a bounded maximiser gives `|s_opt − α| ≤ 1e-6` (5 economies); `c*(α)` beats a 197-point grid of s; α wins in long simulations | Guarantee 7, independently |
| At k*: y constant, `G_t = g`, total output grows at `n + g + ng`, index `= 100(1+g)^t` | Effective vs actual worker |
| Continuous limit: steady-state and path errors first order (fitted 0.95-1.05), exact when n̂ = 0, `(1−ρ)/ε → β`; closed-form z solution satisfies the ODE | Guarantee 8 |
| Baseline and scenario bit-identical (`tobytes`) for `k, y` at `t ≤ T_c` and `c, i` at `t < T_c`; differ at `c_{T_c}` and `k_{T_c+1}`; `s₁ = s₀` reproduces the baseline | Policy timing |
| API: shapes, formulas, timing, logging and hash; corners of the input box stay finite; 23 invalid payloads (bounds, λ = 0 and λ = 5·10⁻⁴, policy year ≥ horizon, unknown fields, NaN/±Infinity) give 422 | Contract |
| Per-run checks (`test_solow_checks.py`): the identity check counts a 1-ulp change in any of k, y, c, i before the change; its note is well formed for `T_c = 0`; the convergence note states the true reason (default run: 80 years = 6.5 half-lives, about 12.7 more needed), and simulating the predicted extra 157 years lands within a factor 2 of 1e-6; `|G − g|` is ~0 at the steady state and uses the final year; non-finite paths or half-life give a 422 domain error, not a 500. Mutation-checked: weakening the λ rule, dropping y from the identity, reading `G_0` and swapping the notes each fail a test | Per-run checks |

### Per-run checks shown in the app
Steady-state residuals for s₀ and s₁ (numerical diagnostic, limit 1e-13), baseline =
scenario before the change (exact identity over k and y for `t ≤ T_c` and c and i for
`t < T_c`, must be 0 mismatches), distance from `k*(s₁)` in the final year and `|G − g|` in
the final year (information only). When the distance is above 1e-6, the note says how many
half-lives have passed and estimates, from the linearisation, how many more are needed. These
describe one run; the guarantees above are what make them meaningful. The form also applies
the λ ≥ 10⁻³ rule before sending; the bound is read from the API contract
(`x-min-effective-depreciation`), and the server stays the authority.

### Observed (2026-10-15, default inputs)
`α = 0.3, s₀ = 0.2, s₁ = 0.3, δ = 0.05, n = 0.01, g = 0.02`: `k*(0.2) = 3.68924`,
`k*(0.3) = 6.58409` (= golden rule, since s₁ = α), `ρ = 0.945506`, half-life 12.37 years,
residuals 1.1e-16.

### Limitations
- A teaching model. Constant exogenous rates, one good, a closed economy, full employment,
  no government or money. Its numbers are illustrative model output, not forecasts.
- Discrete annual timing is a modelling choice; the continuous-time version differs by the
  `ng` term in the steady state and by first-order terms along the path.
- Only one permanent change of the savings rate. Other shocks belong to later Economy Lab
  phases.
- The rounding bounds are empirical (see above).
- Numeric strings such as `"100"` are coerced to numbers by the API, as everywhere in
  SimForge; this is deterministic and does not affect hashes.


---

## `quant.dataset_profile` v1.0.0: CSV import and descriptive profile

### What it computes, and what it does not
A description of the rows in one file: shape, column types, missing and invalid values,
exact duplicate rows, and descriptive statistics. **No statistic is an estimate for a wider
population, a test or a prediction**; the page and the assumptions say so. Counts are exact.
Means, standard deviations and quartiles are computed in double precision and are correct to
rounding, not exact.

### Definitions
| Quantity | Definition |
|---|---|
| Missing cell | Empty after trimming spaces, or exactly (case-sensitive) one of the markers; default `N/A, NA, NaN, None, null` |
| Number | `[+-]?(digits[.[digits]]|.digits)([eE][+-]?digits)?` with ASCII digits, finite in double precision. Not `1,000`, `inf`, `nan`, `1_000`, `1e999` |
| Leading-zero number (`007`) | Not numeric unless the user overrides the column |
| Date | ISO 8601 `YYYY-MM-DD[(T| )HH:MM[:SS[.ffffff]]]` that exists on the calendar; `01/02/2024` is flagged ambiguous and stays text |
| Column type | `empty` (all missing), `numeric`/`date` (every non-missing value is one), otherwise `categorical` with counts of each kind; **mixed** if its values come from at least two of: number-like, date, other text |
| Invalid | A non-missing value that does not fit an *overridden* type; excluded from statistics, never converted |
| Duplicate row | Identical, character for character, to an earlier row; counted, not removed |
| Date summary | Earliest and latest shown as written in the file; "distinct" counts moments in time (`2024-01-01` and `2024-01-01 00:00` count once) |
| Mean, SD | `(1/n) Σx`; `sqrt(Σ(x − mean)² / (n − 1))`, defined for n ≥ 2; exactly 0 when all values are identical (computing it would leave a rounding residue such as 1.7e-17 for three `0.1`s) |
| Quartiles | Hyndman-Fan type 7 (linear interpolation; NumPy default, R default, `QUARTILE.INC`) |
| Histogram | `min(50, ⌈log₂ n⌉ + 1)` equal-width bins (Sturges); last bin includes the maximum |
| Percentages | Of all rows |

### Numerical-analysis issues handled
- **Overflow in sums and squares.** Values are scaled by `2^−e` with `2^e ≥ max|x|` before
  summing. Multiplying by a power of two is exact in binary floating point, so the scaling adds
  no rounding (apart from values more than ~1e300 times smaller than the largest, which become
  subnormal). The first version divided by `max|x|` instead and turned an exact mean of 37125
  into 37124.99999999999; a test now guards this.
- **Results that are not representable.** The true SD of `[−1.7e308, 1.7e308]` is ≈ 2.4e308,
  beyond double precision. It is reported as `null` with a note, never as infinity.
- **Interpolation between extremes.** `a + g(b − a)` overflows for `a = −max, b = max`; the
  quantile uses `(1 − g)a + gb` and clamps to `[a, b]`, which only removes a rounding step,
  because the exact value lies in that interval. The mean is clamped to `[min, max]` likewise.

### What is tested (`backend/tests/quant/`, `tests/api/test_quant_api.py`; 226 tests)
| Check | Kind |
|---|---|
| Mean and SD against `statistics.fmean` / `statistics.stdev` (exact rational arithmetic), quartiles against `statistics.quantiles(method="inclusive")` (type 7), on 20 seeded random samples over 12 orders of magnitude; quantiles against `numpy.quantile(method="linear")` for n = 1-11 | Independent reference |
| Hand-worked examples: `2,4,4,4,5,5,7,9`; `1..7` shows type 7 (Q1 = 2.5) differs from the "median of each half" rule (Q1 = 2); histogram edges and counts for 0..10 | Hand-derived |
| Both bundled samples, every count and statistic derived by hand from the CSV text | Hand-derived (known answers) |
| Extremes: `[1e308]*3`, `[max, max]`, `[−1.7e308, 1.7e308]` (SD `null`), subnormal values, all zeros, one value, constant columns of non-binary values (SD exactly 0) | Overflow and edge cases |
| 39 cell classifications (numbers, leading zeros, non-finite, ISO and impossible dates, ambiguous dates, Arabic-Indic digits, `1_000`, `inf`, case-sensitive markers) and 9 column inferences | Type rules |
| Overrides: numeric on a mixed column (invalid counted with row numbers), date on a numeric column (no statistics), categorical (all valid); missing + invalid + valid = rows | Override rules |
| Parsing: empty, whitespace-only, header-only, UTF-16, invalid UTF-8, NUL bytes, BOM, duplicate or blank names, inconsistent rows with row and line numbers, unclosed quotes, stray quotes inside unquoted fields (which Python's `csv` module would accept), overlong cells, quoted newlines, blank lines, CRLF, three delimiters, the row, column and size limits at and just over each | Malformed input |
| API: the identity (`input_hash`) changes with any byte or any option and not with equivalent options; a sample and an identical upload share it; 13 malformed requests give 422 (bad base64, path-like sample ids, unknown fields, a file name, out-of-range or duplicate overrides, marker limits); a 2 MiB request is accepted, 2 MiB + 1 byte is rejected even though its base64 fits the schema | Contract |
| Body limit: exactly at the limit the body is read and one byte over gives 413, for declared and chunked bodies alike; the 413 carries CORS headers; a small chunked body and the Solow, projectile and health endpoints still work | Contract |
| A numeric sentinel (`-999`) as a marker is missing, not averaged; a one-column file with blank lines carries a warning note | Missing values |
| Privacy: a rejected upload is never echoed back in a 422 error, however small (file content and long strings in the echoed input or field location are replaced by a note); nothing is logged unless asked; a saved record contains the hash, size, options and counts, and no column name, cell value or encoded content (the options do hold any markers the user typed) | Data handling |

### Per-run checks shown in the app
Exact identities, each a count that must be 0: columns where missing + invalid + valid ≠ rows,
numeric columns whose histogram does not hold every valid value, categorical columns whose
listed counts plus "other" do not add up, and distinct + duplicate ≠ rows. Information only:
the number of mixed columns and of invalid values. They check the bookkeeping of one profile,
not whether the data are correct.

### Observed (2026-10-16; Python 3.12.3, NumPy 2.5.4)
A 2.04 MB upload with 40,000 rows and 5 columns (200,000 cells) was profiled in about 0.4 s
through the API in-process, with a response of about 9 KB. The end-to-end test uploads 1.9 MiB
(38,000 rows) through the Next.js proxy successfully.

### Limitations
- UTF-8 only, one header row, a delimiter chosen by the user (not guessed), at most 2 MiB,
  50,000 rows and 100 columns.
- Dates: ISO 8601 only, without time zones; dd/mm vs mm/dd cannot be resolved from a file and
  stays text. There is no date-format override yet.
- Numbers with thousands separators or decimal commas stay text; no locale handling.
- Values are stored as doubles: integers above 2^53 ≈ 9.0e15 are rounded (9007199254740993
  becomes 9007199254740992), and magnitudes below ~5e-324 become 0. Long identifiers should
  stay categorical (they do when they have leading zeros; otherwise override them).
- In a one-column file a blank line is indistinguishable from an empty value. Blank lines are
  skipped and counted, and the column gets a note saying they may be missing values.
- Missing-value markers are a global list, not per column; marker matching is exact.
- No cleaning: nothing is changed or removed. Replayable cleaning recipes are Phase 5.
- The SHA-256 identifies bytes; it says nothing about how the data were collected or whether
  they are accurate.
- Multi-user isolation is not claimed: there is no authentication, and the experiment log
  (when used) is visible to everyone on the deployment. The server stores no dataset.

## Reproducibility and replay (run record v2, roadmap 1.4)

`POST /api/v1/experiments/{run_id}/replay` reruns a stored run with its stored inputs and the
same model version, and returns a verdict. Two hashes answer two questions:

| Hash | Question | Definition |
|---|---|---|
| `input_hash` | Same question? | SHA-256 of the canonical JSON of the inputs that affect the numbers |
| `output_digest` | Same answer? | SHA-256 of the canonical JSON of the full response without its run metadata (and, for the angle sweep, without the echoed launch angle, which a sweep does not use) |

Canonical JSON writes every float in its shortest exact form, so **equal digests mean every
output value is bit-identical**. A rebuilt request must reproduce the stored input hash, or
the replay is refused (409) before anything is recorded.

| Verdict | Basis | Meaning |
|---|---|---|
| `identical` | `output_digest` | The digests match: every output value is bit-identical |
| `identical` | `summary_only` | A v1 record (no digest): every stored summary value is identical; other outputs could not be compared |
| `within_tolerance` | `summary` or `summary_only` | Every summary value agrees within its declared tolerance; the field furthest from agreement is reported. Outputs outside the summary (time series) are **not** compared |
| `differs` | either | A summary value is outside its tolerance, or the summaries have different fields |

Every verdict also lists any environment differences (library versions, platform, git
commit, Python implementation). Refusals, each with its own test: unknown run (404), unknown
model (422), model version changed since the run (409; a rerun would be a different model, so
it would not be a reproduction), stored inputs no longer valid (422), inputs no longer hashing
the same (409), uploaded dataset not re-supplied (422), re-supplied file with a different
SHA-256 or size (422, refused **before** it is read), a file for a model that takes none
(422), a domain error (422), a body over the size limit (413).

### Declared tolerances (used only when the digests are unavailable or differ)
Each model declares, in advance and with a reason, how far each stored summary value may move
between environments. A test checks that every stored field matches exactly one rule.

| Model | Fields | Rule | Reason (short) |
|---|---|---|---|
| projectile | `analytical.*` | 1e-12 relative | closed forms; a few rounding errors of ~1e-16 |
| projectile | `numerical.*` values | `10·(rtol·|x| + atol)` | an adaptive solver's step decisions can flip, moving results by up to its error control |
| projectile | step and evaluation counts, solver settings | exact | counts and copies of inputs |
| projectile | `comparison.*` (error estimates) | absolute, `10·(rtol·|x| + atol)` or `10·(rtol + atol/|x|)` | error estimates are rounding-sized, so only an absolute tolerance makes sense |
| integrators | horizon; orders; fit points; theoretical order | 1e-12 rel; 1e-6 rel; exact; exact | fits use only points far above rounding |
| integrators | finest max position error | 1e-9 m absolute | rounding-dominated at the finest RK4 step; ≲5e-10 m over 5e4 steps |
| angle sweep | best angle; best range; vacuum values | 1e-5° abs; 1e-10 rel; 1e-12 rel | Brent's ~1e-6° tolerance at a flat maximum |
| Solow | k\*(s₀), k\*(s₁) | `2 × 8u·(1/(1−α)+2)` relative | twice the empirical k\* bound above |
| Solow | final capital | `2 × 64u/(1−ρ)` relative | twice the empirical path bound above |
| Solow | golden-rule rate; half-life | exact; 1e-12 rel | a copy of α; a closed form |
| dataset profile | every field | exact | counts and labels |

**What is and is not established.** Measured: every model's runs replay **bit-identically**
in this environment (the locked library versions on linux-x86_64; a test runs all six cases).
**Not measured:** whether results differ on other machines or library versions, so the
tolerances are reasoned from each method's error control and the empirical rounding bounds
above, not from cross-machine data. They are a declared contract, to be revised if real
cross-environment replays show otherwise.

**Observed (2026-10-22), on a real migrated log.** The end-to-end test database had been
written by earlier sessions under schema v1 (41 runs). Starting the app migrated it (backup
kept; all 41 rows preserved as v1). Replaying every run in a copy: all 39 physics and economy
runs came back `identical`: 33 v1 runs compared on their summaries, 6 v2 runs on their output
digests. The 10 dataset profiles were all of uploaded files, and each replay was refused with
a request to supply the same file again.

### Tests
`tests/test_migration.py` (a real v1 log: backup, exact preservation of old rows, idempotent,
newer schema refused untouched, a failed migration rolls back completely: without a real
transaction it does not, which the test caught), `tests/api/test_registry.py` (one entry per
model; stored inputs rebuild the same input hash), `tests/api/test_run_record_v2.py` (the
digest is recomputable from the response alone; it ignores run metadata),
`tests/api/test_golden_digests.py` (fixed inputs keep their pinned digest per model version: a
regression guard, not evidence of correctness; a 1-ulp change in Solow's initial capital fails
it) and `tests/api/test_replay.py` (every verdict, every refusal, saving and linking). Mutation
checks: ignoring the digest, a tolerance made 10¹² times looser, and dropping the replay link
each fail a test.

### Known limitations
- Replays of v1 records (before 1.4) compare only the stored summary.
- `within_tolerance` covers the summary only; time series are not stored, so not compared.
- Model versions were not bumped when PRs #8 and #9 changed some outputs (the t = 0 landing
  fix, check notes). A v1 record affected by those fixes replays as `differs`, which is true.
- Deleting runs is deferred: with no authentication, a delete endpoint would let anyone
  delete anyone's runs. To remove runs, stop the server and edit or delete the SQLite file.
