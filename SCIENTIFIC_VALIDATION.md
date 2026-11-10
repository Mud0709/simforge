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
  closed-form 2-D solution. That is a separate model, `physics.projectile.quadratic_drag`
  (below), validated against the exact vertical flight, limits, invariants and proved bounds
  instead of an exact 2-D answer.
- **Interpolation error is mixed in, not separated out.** Error metrics are evaluated at the
  solver's accepted step nodes, but the last node (the landing) and the event-located apex
  come from the dense-output interpolant, so they include interpolation error. Plotted curves
  also come from the interpolant. Interpolation error is not reported separately.
- **The integration cap depends on the exact solution.** The numerical run uses `2 × T_exact`
  as its integration cap. The answer is found independently. (The quadratic-drag model, which
  has no exact flight time, uses twice a proved upper bound instead.)
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
- Linear drag only. Quadratic drag has its own sweep model, `physics.projectile.quadratic_angle_sweep` (roadmap 2.2, below); the two sweeps are not compared beyond their shared vacuum limit.
- The single-peak property is checked on the tested cases, not proven in general. If a curve
  ever had two peaks, the refinement could miss the global maximum by up to one grid step.
- Only the launch angle is swept. Other parameters are fixed.

---

## `physics.projectile.quadratic_drag` v1.0.0: projectile motion with quadratic drag

Roadmap 2.1. The plan, with the decisions that changed while building, is
`docs/plans/ROADMAP_2_1_PLAN.md` ("Amendments after building"). Learning guide: Part 18.

### Model
A point mass `m` under uniform gravity `g` with quadratic drag `F = −c|v|v`, `c` in kg/m
(API field `drag_constant`; not the linear model's `b` in kg/s, and not the dimensionless
`C_d` in `c = ½ρC_dA`). With `κ = c/m` (1/m):

```
dvx/dt = −κ |v| vx          dvy/dt = −g − κ |v| vy          |v| = √(vx² + vy²)
```

State `[x, y, vx, vy, W]`, where `W` is the work done against drag, integrated from
`dW/dt = c|v|³` (coded from that formula, **not** from the force function, so that the energy
balance can catch a wrong force law). Derived quantities: terminal speed `v_t = √(mg/c)`
(m/s), time scale `τ = v_t/g` (s). `c = 0` means vacuum. SI units throughout; launch angle in
degrees at the API boundary; an exactly vertical launch (90°) has `vx₀ = 0` exactly (not
`cos(π/2) ≈ 6e-17`). Engine files in `backend/src/simforge/physics/projectile/`:
`quadratic_reference.py` (closed forms, invariant, bounds), `quadratic_numerical.py` (the ODE
solve), `quadratic_model.py` (guard, references, diagnostics, checks, assumptions),
`quadratic_schemas.py` (the API contract and input rules).

### No exact 2-D solution: what replaces it
The speed `|v|` couples the two components, so the 2-D motion has no general closed form and
is solved numerically: SciPy `solve_ivp` (RK45, DOP853 (default) or Radau; default
`rtol = atol = 1e-10`), a terminal landing event with `direction = −1` and the linear model's
"launch instant counts as above ground" guard, an apex event on `vy`, dense output. In place of
an exact answer it is checked against:

| | Reference | What it constrains | Genuinely 2-D? |
|---|---|---|---|
| R1-R3 | Exact vertical solution (`tan` rise, `tanh` fall, full flight) | Solver accuracy and events, at θ = 90° only | No (`vx = 0`) |
| R4 | Terminal speed `√(mg/c)` | Long-time behaviour | No (the velocity tends to `(0, −v_t)`) |
| `c → 0` | Textbook vacuum formulas, written in the tests | The drag-free limit | Yes, but drag-free |
| R5 | Energy balance `KE + PE + W = E₀` | Consistency of motion and dissipation | Yes |
| R6 | Hodograph invariant | The coupling of x and y | Yes |
| R7 | Two bounds (speed, flight time), plus the drag-time bound | Integration cap and stiffness guard; must hold on every step node | Yes |

**No comparison with linear drag beyond the shared vacuum limit**: no value of `b` makes `bv`
equal `cv²` except at one speed, so a "low-speed agreement" test would need an arbitrary
matching speed and an underived tolerance.

### Mathematical guarantees (proved on paper; the tests check the implementation obeys them)
Derived in the plan ("Reference formulas") and, for the drag-time bound, in the docstring of
`quadratic_model.drag_time_bound`. **Not checked against any literature source.**

1. **R1, rise** (`v > 0`): `v(t) = v_t tan(φ₀ − t/τ)`, `φ₀ = arctan(v₀/v_t)`; apex time
   `t_a = τφ₀`; `y(t) = h + (v_t²/g) ln(cos s + (v₀/v_t) sin s)`, `s = t/τ`; apex height
   above launch `H = (v_t²/2g) ln(1 + v₀²/v_t²)`.
2. **R2, fall from rest** through a drop `Y`: `w(s) = v_t tanh(s/τ)`, drop
   `(v_t²/g) ln cosh(s/τ)`; with `X = gY/v_t²`, fall time `τ arcosh(eˣ)` and impact speed
   `v_t √(1 − e^(−2X))`.
3. **R3, vertical launch**: `Y = h + H`, `T = t_a + s_L`. From the ground the impact speed is
   `v₀v_t/√(v₀² + v_t²) < v₀`, and the fall takes longer than the rise. As `c → 0`:
   `t_a → v₀/g`, `H → v₀²/2g`, impact speed `→ v₀`.
4. **R4, terminal speed**: `v_t = √(mg/c)`; from R2, `v_t − w ≈ 2v_t e^(−2s/τ)`.
5. **R5, energy balance**: `d/dt(½mv² + mgy) = −c|v|³`, so `KE + PE + W = E₀`.
6. **R6, hodograph invariant** (`vx₀ > 0`):
   `I = 1/vx² + (κ/g)·[v·vy/vx² + asinh(vy/vx)]` is constant (s²/m²). `vx` never changes
   sign, so `I` is defined for the whole flight; it is undefined for a vertical launch.
7. **R7, bounds**: (i) speed `≤ max(v₀, v_t)` throughout; (ii) flight time
   `≤ T_bound = vy₀/g + T_fall`, with `T_fall` the exact linear-drag time to fall from rest
   through `h + vy₀²/2g` with `k = κ·max(v₀, v_t)`. Exact in vacuum, loose with drag.
8. **Drag-time bound**: `S = ∫κ|v| dt ≤ ln(1 + κ·vx₀·T_bound) + ln(1 + vy₀²/v_t²) + κh`
   (from `|v| ≤ |vx| + |vy|`, `vx ≤ vx₀/(1 + κvx₀t)` and the R1 climb bound). Exact for a
   vertical flight; since `S ≥ κh`, it exceeds `S` by at most the two logarithms.

**Smoothness caveat (proved):** `|v|v` is once but not twice differentiable at `v = 0`, which
only a vertical launch reaches. The vertical tests allow 100 × rtol and state this reason.

### Numerical-analysis issues handled
Every closed form is written as *the vacuum value times a correction factor* that tends to 1
as `v_t → ∞` (for example `t_a = (v₀/g)·atan(r)/r`, `r = v₀/v_t`), so vacuum is the same code
path (no special case, no `0·∞`), weak drag does not cancel, and nothing overflows:
- `H` and `y(t)` use `log1p` (`ln(1 + r²)` would round `1 + r²` first);
  `test_naive_apex_height_loses_digits_for_weak_drag` shows the naive form losing digits.
- `ln cosh u` is evaluated as `log1p(2 sinh²(u/2))` for `u ≤ 1` and `u − ln 2 + log1p(e^(−2u))`
  above, with the series `1 − u²/6` below `u = 1e-4`.
- **The fall time is not computed in the plan's form** `τ asinh(√expm1(2X))`, which overflows
  once `2X > 709.8` (strong drag, long drops): it uses `arcosh(eˣ) = X + log1p(√(1 − e^(−2X)))`,
  positive terms only (`test_plan_form_of_the_fall_time_overflows_for_strong_drag`).
- `v_t` stays finite when `mg/c` overflows (tiny or subnormal `c`): square roots first.
- The invariant uses `asinh(vy/vx)` instead of `ln((v + vy)/vx)`, which cancels when
  `vy ≈ −v`; its residual is normalised by `max(1/vx²)` (below).

### What is tested
Every expected value comes from an independent source: the equations of motion written out
in the test, hand-derived Taylor limits, separately derived closed forms, 50-digit stdlib
`decimal` evaluations, or a test-local SciPy integration with its own right-hand side.

**Reference formulas** (`backend/tests/physics/test_quadratic_reference.py`):

| Check | Reference | Tolerance (each justified in the test) |
|---|---|---|
| `c v_t² = mg`; `v_t` finite when `mg/c` overflows | Force balance; 50-digit `decimal` | rel 1e-15 |
| Rise and fall curves satisfy their ODEs | Central differences, truncation and rounding worked out per case | rel 1e-8 (+ abs 1e-7 where the rate passes 0) |
| Fall time and impact speed consistent with the fall curve | Different formulas for the same numbers | rel 1e-14 |
| Impact speed from the ground `= v₀v_t/√(v₀² + v_t²)`; fall longer than rise | Algebra; `asinh r − atan r > 0` | rel 4e-15; strict |
| Weak drag: `r²` Taylor corrections to `t_a`, `H`, impact speed | Hand-derived series | rel 2e-15 (the correction itself ≥ 1e6× larger) |
| `c = 0`, `1e-25`, `1e-320` → textbook vacuum flight | Textbook formulas | rel 4e-15 |
| Apex time and height, rise curve, fall time, impact speed, fall distance | 50-digit `decimal` of the plain formulas (weak drag down to `X ≈ 1e-12`, strong to `X ≈ 1e9`) | rel 2e-15 to 6e-15 |
| `I` is constant along `−κ|v|v`; the wrong coupling drifts it | Rate of change from the equations of motion, with a rounding budget | budget < 1e-6 of the scale; mutant ≥ 1e-2 |
| Speed bound on exact vertical speeds; on 2-D flights | R3; test-local DOP853 at 1e-12 | rel 2ε; rel 1e-9 |
| Flight-time bound: exact in vacuum; equals the proved formula; holds for exact vertical and 2-D flights | Textbook; a 50-digit bisection of the linear-drag fall; R3; test-local DOP853 | rel 1e-14; rel 1e-14; strict |
| Non-finite and out-of-domain inputs rejected | Contract | — |

**Integrator** (`backend/tests/physics/test_quadratic_numerical.py`; all three methods
unless noted, default `rtol = atol = 1e-10`):

| Check | Reference | Tolerance |
|---|---|---|
| Vertical launches (3 cases): flight time, apex time, apex height, impact speed; `x` and `vx` exactly 0 | R1-R3 | rel 1e-8 (100 × rtol, widened for the apex) |
| The vertical path follows the rise and fall curves at every step node | R1, R2 | 3e-7 m (100 × (rtol·|y| + atol)) |
| `c = 0` (3 angle/height cases): time, range, height, impact speed; `W` exactly 0 | Textbook vacuum formulas in the test | rel 1e-12 |
| Range deviation from vacuum is first order in `c` (`c = 1e-4, 1e-6, 1e-8`; DOP853 at 1e-13) | Limit | ratio 100 within 2% |
| Long fall (90° and 30°, ~200 τ) ends at `(0, −v_t)` | R4 | rel 1e-8 |
| Energy balance closes (5 2-D cases) | R5 | 1e-8 of `E₀` |
| Invariant conserved (4 cases); normalised by `I₀` it is meaningless in a long fall (> 1e-3) while the chosen residual is < 1e-8 | R6 | 1e-8 |
| Speed and flight-time bounds on every step node (5 cases) | R7 | rel 1e-8; strict |
| Shallow launches (0.001° to 1°) land at the real time, not t = 0 | Test-local DOP853 at 1e-12 | rel 1e-6 |
| Horizontal launch starts at its apex | Exact | exact |
| Error falls as rtol tightens (1e-4 → 1e-10; RK45): vertical flight time and 2-D energy residual | R3; R5 | > 1e3 × reduction |
| `drag_acceleration(3, 4, 0.1) = (−1.5, −2)` | Hand-worked | rel 1e-15 |
| **Wrong-coupling mutant** (`−κ|vx|vx`, `−κ|vy|vy`; DOP853): passes the vertical, vacuum, long-fall and (here) R7 checks; caught by R5 and R6 (> 1e-3, measured 0.16-0.34 and 0.16-0.24); breaks the speed bound in a horizontal launch below `v_t` (> 1%, measured 1.85%) | Mutation | — |

**Model run** (`backend/tests/physics/test_quadratic_model.py`): the guard refuses a 100 km
fall at `v_t = 3 m/s` for RK45 and DOP853 with a message naming the method, the 1e4 limit and
Radau, and Radau runs it with no check failing; the guard accepts the case the plan's rule
refused (`v₀ = 1000 m/s`, 60°, `v_t = 30 m/s`: plan rule 6.2e5, true `S` = 6.7) in under 1000
RK45 steps; the drag-time bound holds against a test-local integration of `S` (4 cases, slack
< 30) and is exact for vertical flights (rel 1e-10); vacuum runs have no terminal speed, no
NaN or infinity anywhere, and no speed-bound check; the vacuum comparison matches the linear
model's closed form with `b = 0` (a different code path); `vertical_reference` only at exactly
90°; the invariant is `null` with a reason for a vertical launch and for a hand-made solution
whose `vx` is ≤ 0 or makes `1/vx²` or `v·vy/vx²` overflow; in a ~200 s fall the invariant check
is either informational or passes, never fails; checks are present, labelled and pass by
default; the invariant check does not fail accurate nearly vertical runs or a long fall at
`atol = 0.1`; the checks **fail** (energy and invariant) with the wrong-coupling mutant while
the loose flight-time bound still passes; series end at landing and the vacuum series has its
own grid.

**API** (`backend/tests/api/test_quadratic_drag_api.py`, `test_quadratic_drag_limits.py`):
a complete labelled default response; strict JSON in vacuum and vertical runs; terminal speed
through `c v_t² = mg`; the vacuum run against the textbook; drag shortens the flight; the
vertical comparison (3 solver/height cases); `NaN`, `±Infinity`, out-of-bound and unknown
inputs rejected; a flat launch from the ground refused; a stiff explicit run gets an
explanatory 422; identical inputs give identical hashes and results, and the hash ignores
`save_experiment`; the stored summary has the same shape for every run; one tolerance rule per
stored field for a 2-D, a vertical and a vacuum run, each replaying `identical`; the value
rules survive emulated last-bit differences at `rtol = 1e-13` (5 seeds). Each input rule is
tested at its boundary with values worked by hand, and the suggested `atol` in the refusal is
itself accepted. **Corners:** every corner of (mass, speed, `c` = 0 or largest allowed, `g`,
height, angle 0/1e-3/90) with every method at the tightest (`1e-13, 1e-14`) and loosest
allowed tolerances either runs (finite, positive flight time; vacuum flight time to rel 1e-6)
or gets a 422 with a reason; never a 500, and no request over 10 s. Tight-tolerance Radau
skips 26 corners that repeat another corner's computation, with a check that the rest still
cover every value of every axis.

**Registry and reproducibility:** a case appended to `tests/api/test_registry.py` (2-D,
`c = 0.02 kg/m`, 30°), so the registry, replay (`test_replay.py`), recompute
(`test_run_outputs.py`) and golden-digest (`test_golden_digests.py`) tests pick it up; one
golden entry appended to `tests/api/golden_runs.json`, the six existing entries unchanged.

### Per-run checks shown in the app
Every response carries a `checks` list (decision 12): **energy balance**
(`max |KE + PE + W − E₀| / E₀` over the step nodes); **hodograph invariant**
(`max |I − I₀| / max(1/vx²)`, or an informational row giving the smallest `vx` when `I` is
undefined); **speed bound** (largest speed / `max(v₀, v_t)`, only with drag); **flight-time
bound** (flight time / `T_bound`); for an exactly vertical launch, **flight time against R3**;
and an informational **drag time** row (the bound on `S`). Thresholds:

```
threshold = 1e4 × accuracy + 1e-9        (bounds: 1 + that)
accuracy  = rtol + atol/v₀               (energy, bounds, vertical comparison)
accuracy  = rtol + atol/min(vx₀, v_t)    (invariant)
```

The factor 1e4 is **empirical**, not a theorem: an adaptive solver's global error is not
bounded by rtol. On 2728 runs the worst residual / accuracy was 490 (energy), 8.5e3
(invariant), 45 (speed bound), 61 (vertical flight time). The invariant uses its own scale
because the slice 2 review found that with `atol/v₀` RK45 failed *correct* nearly vertical
runs at default settings (`v₀ = 1 m/s`, 89.99°: `vx` off by 3.5e-6 relative, confirmed with
DOP853 at 1e-13). Re-measured on 10 080 runs (5 speeds, 8 angles up to 89.999° and 90°,
3 heights, `v_t` ∈ {1, 20, 1e3, ∞} m/s, 3 methods, 7 (rtol, atol) pairs from (1e-13, 1e-14)
to (1e-6, 0.1)): no check failed; the largest value / threshold was 0.081 (invariant), 0.012
(energy), 0.006 (speed bound) and 0.18 (vertical flight time). One machine, recorded in the
comment above `GLOBAL_ERROR_FACTOR` in `quadratic_model.py`.

`terminal_speed` (exact; `null` in vacuum) and `vacuum` (the same launch with no drag, exact)
are labelled "exact"; `vertical_reference` (only at exactly 90°) gives the exact R3 values and
the numerical errors against them; every numerical value is labelled with its solver and
tolerances.

### Input limits, the integration cap and the stiffness guard
Single fields, as the linear model: speed 1e-3 to 1e4 m/s, angle 0 to 90°, height 0 to
1e5 m, mass 1e-6 to 1e6 kg, `g` 0.01 to 1000 m/s²; `c` from 0 (vacuum) to 1e6 kg/m. Combined
rules (`quadratic_schemas.py`), each tested at its boundary:

| Rule | Why | Evidence |
|---|---|---|
| `κ·max(v₀, v_t) ≤ 1e4 s⁻¹`, computed as `max(κv₀, √(κg))` | The largest drag rate in the flight (R7 i), the same meaning as the linear `k ≤ 1e4 s⁻¹`; no `0·∞` in vacuum | Proved bound plus the linear model's limit |
| `atol ≤ 0.01·min(v₀, v_t)` | Far above the smallest velocity scale the solver does not control the velocity | Measured (slice 3, corners grid): ≤ 0.2 s up to 1× the scale, 0.53 s at 5×, up to 10 s at 10×, 20 s timeouts and overflow at 100-1000× (mostly Radau); at 10% one RK45 run missed the exact vertical flight time by 1.1%; 1% is the largest fraction at which every grid run passed its own checks |
| Drag-free flight ≥ 1 µs; no flight at 0° from 0 m | SciPy locates the landing only to about 1e-15 s; shorter flights crashed the run (a zero cap, or the bound's root search failing). With drag rates ≤ 1e4 s⁻¹, drag changes so short a flight by under 1% | Found by the corners test (angles 1e-100° and 1e-320° gave 500s before the rule) |

**Integration cap:** `2 × T_bound` (exact in vacuum; twice it, so the landing is never at the
very end of the interval, where rounding can hide the sign change). **Stiffness guard:**
explicit methods (RK45, DOP853) are refused with a 422 when the drag-time bound exceeds 1e4;
Radau has no drag-time limit (it is L-stable). The plan's rule, `κ·max(v₀, v_t)·T_bound`
against 1e4 and 1e7, was replaced because it multiplies two loose bounds. Observed in slice 2
(one machine; `quadratic_model.py` docstring) on a 1007-point grid within the limits: the
plan's rule refused 323 explicit runs, **193 of which finish** in at most 38 000 evaluations;
the drag-time rule refused 130, none of which finished within 250 000 evaluations; every run
the plan's Radau limit would have refused finished in under 0.5 s. For DOP853 above `S = 100`
the cost was 2.5 to 16 evaluations per unit of `S`.

### Observed accuracy
Measured on 2026-10-27 with Python 3.12.3, NumPy 2.5.4 and SciPy 1.18.1 on linux-x86_64
(Intel Xeon @ 2.10 GHz), with scratch scripts, not repository tests. Errors are against an
independent integration with its own right-hand side (DOP853 at `rtol = atol = 1e-13`;
DOP853 and Radau at that setting agreed to 4e-13 relative or better). Observed, one machine;
not guarantees for other inputs.

`v₀ = 20 m/s`, `θ = 45°`, `h = 3 m`, `m = 1 kg`, `g = 9.80665 m/s²`, `rtol = atol = 1e-10`:

| c (kg/m) | v_t (m/s) | Method | Rel. error, flight time | Rel. error, range | Max energy residual (×E₀) | Max invariant residual | Steps |
|---|---|---|---|---|---|---|---|
| 0 | ∞ | RK45 | 1.4e-16 | 3.3e-16 | 1.2e-16 | 0 | 5 |
| 0 | ∞ | DOP853 | 1.7e-15 | 3.9e-15 | 2.1e-15 | 0 | 4 |
| 0 | ∞ | Radau | 1.4e-16 | 6.5e-16 | 6.2e-16 | 0 | 5 |
| 0.01 | 31.3 | RK45 | 2.8e-13 | 2.4e-12 | 1.3e-11 | 9.6e-12 | 42 |
| 0.01 | 31.3 | DOP853 | 9.2e-12 | 8.5e-12 | 1.9e-12 | 3.3e-12 | 11 |
| 0.01 | 31.3 | Radau | 3.2e-13 | 4.8e-13 | 3.6e-13 | 2.4e-12 | 282 |
| 0.1 | 9.90 | RK45 | 8.1e-12 | 2.2e-12 | 3.0e-12 | 3.5e-11 | 84 |
| 0.1 | 9.90 | DOP853 | 1.1e-11 | 3.9e-12 | 2.9e-12 | 6.8e-11 | 21 |
| 0.1 | 9.90 | Radau | 1.4e-12 | 4.6e-13 | 2.3e-12 | 5.7e-12 | 513 |

(As for the linear model, the vacuum rows say little: the vacuum path is a quadratic in `t`,
which these methods integrate exactly apart from rounding.)

Worst over 54 2-D cases (`v₀` ∈ {20, 100, 1000} m/s, θ ∈ {15, 45, 75}°, `h` ∈ {0, 10} m,
`v_t` ∈ {5, 20, 100} m/s, default tolerances):

| Method | Flight time | Range | Energy residual | Invariant residual (none null) | Steps (median, max) |
|---|---|---|---|---|---|
| RK45 | 1.8e-11 | 2.7e-11 | 8.5e-11 | 7.7e-11 | 144, 360 |
| DOP853 | 3.0e-11 | 2.7e-11 | 1.6e-11 | 5.8e-10 | 36, 89 |
| Radau | 2.5e-12 | 2.7e-12 | 5.7e-12 | 2.1e-11 | 758, 1763 |

Vertical launches against the exact R3 values, worst relative error over 18 cases (`v₀` ∈
{5, 30, 300} m/s, `h` ∈ {0, 40} m, `v_t` ∈ {3, 20, 100} m/s, default tolerances):

| Method | Flight time | Apex time | Max height | Impact speed |
|---|---|---|---|---|
| RK45 | 1.2e-10 | 1.6e-9 | 2.7e-11 | 2.2e-10 |
| DOP853 | 1.2e-9 | 4.4e-10 | 2.3e-11 | 2.7e-9 |
| Radau | 6.4e-12 | 5.4e-12 | 3.5e-13 | 8.1e-12 |

The vertical errors of the explicit methods (up to ~10-30 × rtol) are larger than their 2-D
errors; this is consistent with the smoothness caveat at the vertical apex, but the cause was
not separated. Any single run's own residuals appear in its response under `diagnostics`.

**Earlier observations, kept for the record.** During planning, a scratch DOP853 integration
at 1e-12 agreed with R1-R3 to 5e-11 relative on four cases, and a learning-guide scratch RK4
(step 1e-4 s, tennis-ball values) closed the energy balance to 5e-15 of `E₀` with the correct
law and 0.15 with the wrong one. These checked the derivations, not SimForge's code.

### Replay tolerances
Declared in `_quadratic_tolerances` (`api/routes/physics.py`), one rule per stored field
(tested). Wherever a rule uses rtol, it uses **max(rtol, 1e-10)**: below 1e-10 rounding, not
the solver's error control, sets the accuracy. Measured in the slice 3 review by emulating
another CPU (each drag evaluation multiplied by 1 ± 1 or 2 ulp; 1728 reruns over speeds,
angles up to 90°, heights, drag, all methods, rtol 1e-13 to 1e-3): at rtol = 1e-13 results
moved by up to 1e-10 relative (a nearly vertical flight's range, DOP853) and one Radau energy
residual from 1.2e-13 to 6.5e-10, up to 650 times the unfloored rule. At rtol ≥ 1e-10 (the
default and the golden run) the floor changes nothing.

| Field | Rule | Reason (short) |
|---|---|---|
| `numerical.*` values | `10·(rtol·|x| + atol)` | an adaptive solver's step decisions can flip on another machine (the linear model's rule) |
| `numerical.n_steps`, `n_rhs_evaluations`, method, rtol, atol | exact | counts and copies of inputs |
| `terminal_speed`, `vacuum.*` | 1e-12 relative | closed forms; `null` must stay `null` |
| `diagnostics.max_energy_balance_residual` | absolute `10·(rtol + atol/v₀)` | the check's own accuracy scale |
| `diagnostics.max_invariant_residual` | absolute `10·(rtol + atol/min(vx₀, v_t))`; exact (`null`) for a vertical launch | the check's own accuracy scale |
| `diagnostics.drag_time_bound`, `flight_time_bound` | 1e-12 relative | closed forms and a Brent root converged to ~1e-15 |

### Known limitations
- Constant `C_d` (so constant `c`): no variation of drag with speed, no spin or lift, no wind,
  no buoyancy. Validation shows the equations are solved, not that they describe a real ball.
- **No exact 2-D reference.** The 2-D evidence is consistency (R5, R6, R7, `c → 0`) and
  agreement with an independent integration, not a comparison with a true answer.
- **The per-run thresholds are empirical** (1e4 × the requested accuracy), measured on one
  machine on the grids above; not a theorem.
- **Exact step counts may differ on another CPU.** The counts are replayed exactly by design
  (a different step sequence is a different computation), so a replay on another machine can
  report `differs` on `n_steps` or `n_rhs_evaluations` alone; the emulation above deliberately
  leaves them out. The quadratic case's behaviour on CI's CPU is not recorded here.
- **The invariant can switch between a number and `null` at extreme settings.** In a very long
  fall the true `vx` decays far below atol (to ~1e-85 m/s in a ~200 s fall), where the solver
  does not control its sign: on the pinning machine DOP853 dips to −9e-14 m/s (so `null`),
  another CPU may keep it positive. Both are correct, but a replay then compares a number with
  `null`, which no tolerance absorbs (`differs`).
- **The atol rule is conservative for slow launches.** It ties atol to `min(v₀, v_t)`, so a
  slow launch must use a small atol even where a larger one would have been fast and accurate;
  it was set on a grid of corners, not derived.
- **T_bound is loose**: up to ~7e5 times the flight time within the input limits (slice 2
  measurement; the planning estimate of ~100× was far too low). It is used only as the cap and
  inside the logarithm of the drag-time bound, and its looseness made the plan's guard refuse
  feasible runs. The drag-time bound's slack is at most a few tens (measured ≤ 27 on the
  1007-point grid), so the guard can still refuse a run whose true `S` is a little under 1e4.
- **The invariant residual dilutes early errors**: dividing by the largest `1/vx²` makes
  errors early in the flight, where `1/vx²` is small, count less.
- **Reopening a run does not restore `n_samples`** on either projectile page: the pages have
  no such field and send none, so the default 400 applies. A run saved through the API with another `n_samples`
  reopens with 400, which is a different question (different input hash); replay and
  recompute use the stored value.
- About 40 lines of event logic are duplicated from the linear solver until roadmap 2.4.
- The hodograph-method literature was not checked.

---

## `physics.projectile.quadratic_angle_sweep` v1.0.0: range against launch angle with quadratic drag

Roadmap 2.2. The plan, with the decisions that changed while building, is
`docs/plans/ROADMAP_2_2_PLAN.md` ("Amendments after building", B1-B10). Learning guide:
Part 19. Engine: `backend/src/simforge/physics/projectile/quadratic_angle_sweep.py` (pure);
request and response at the end of `quadratic_schemas.py`; route and registry entry at the
end of `api/routes/physics.py`; endpoint `POST /api/v1/physics/projectile/quadratic-drag/angle-sweep`.

### What it computes
For fixed speed, height, mass, drag constant `c`, gravity and solver settings, the range is
computed at `n_angles` evenly spaced angles from 0° to 90° (10 to 361, default 91). There is
no formula for a quadratic-drag range, so **every point is one full 2.1 run**
(`quadratic_model.run`, the `physics.projectile.quadratic_drag` model above), with the setup
built exactly as the 2.1 route builds it. 0° from the ground is not run (no flight: range,
time and height exactly 0); 90° is exactly vertical (range exactly 0). The best grid point is
then refined by SciPy's bounded Brent search (`xatol = 1e-7°`) on its neighbouring interval,
and the grid point is kept if it beats the refinement. Reported alongside, all **exact**: the
drag-free range at every grid angle, the drag-free optimum `tan θ* = v₀/√(v₀² + 2gh)`,
`R* = (v₀/g)√(v₀² + 2gh)`, and the terminal speed `√(mg/c)` (`null` in vacuum).

Labels in the response: `ranges`, `flight_times`, `max_heights`, `best_angle_deg` and
`best_range` are **numerical**; `vacuum_*` and `terminal_speed` are **exact**;
`best_angle_uncertainty_deg` is an **estimate, not a bound** (below).

Symbols: `κ = c/m` (1/m), `v_t = √(mg/c)` (m/s), and the dimensionless drag strength
**`ε = κv₀²/g = (v₀/v_t)²`** (0 in vacuum; 0.41 at the 2.1 defaults `v₀ = 20 m/s`,
`c = 0.01 kg/m`, `m = 1 kg`).

### Mathematical results (proved on paper)
1. **RS1, vacuum.** `R(θ) = v₀cos θ·(v₀ sin θ + √(v₀² sin²θ + 2gh))/g`, maximal at the
   closed-form optimum above (45° and `v₀²/g` from the ground). Textbook.
2. **RS2, consistency.** Each sweep point *is* a single 2.1 run at that angle: true by
   construction (the sweep calls the 2.1 model), so it holds bit for bit on one machine.
3. **RS3, weak drag from the ground, first order in ε.**
   `R(θ) = (v₀²/g)·[sin 2θ − ε F(θ)] + O(ε²)` with
   `F(θ) = c s² + c³ s A + c(1 + s²)/4 − c⁵A/(4s)` (`c = cos θ`, `s = sin θ`,
   `A = asinh(tan θ)`), so
   `θ* = 45° − 6.0183°·ε + O(ε²)` and `R*/(v₀²/g) = 1 − 0.783976·ε + O(ε²)`, with
   `F(π/4) = 7/(8√2) + (3/16) ln(1 + √2)` and `F'(π/4) = (3√2 − ln(1 + √2))/8 = 0.420158`.
   **Provenance:** derived by hand for the 2.2 plan (regular perturbation of the vacuum path
   about its apex); independently re-derived by the slice 1 reviewer by a different
   perturbation route (agreement in `F(θ)` to 4.4e-16); **not checked against any literature
   source**. The `O(ε²)` remainder is **not bounded**, so how small ε must be for "weak" is not
   quantified.
4. **"The best angle is below 45° and falls as drag grows."** Since `F'(π/4) > 0`, the best
   angle from the ground is below 45° **to first order in ε** (proved for weak drag only). For
   stronger drag, from a height, and for "keeps falling as drag grows", the evidence is
   **observed** on measured grids (below), not proved.
5. **RS4, flatness.** Near the top `R(θ) ≈ R* − ½K(θ − θ*)²`, `K = |R''(θ*)|` (m/rad²). If the
   computed curve is within `ε_R` of the true one near the top, its maximiser lies within
   `2√(ε_R/K)` rad of `θ*`, *to the quadratic approximation*. This is the basis of `u` below;
   the step from it to `u` uses an unproved error scale, so `u` is not a proved bound.

### The accuracy estimate u (an estimate, not a bound)
`u = 2√(ε_R/K)` in degrees, with `ε_R = 10·(rtol·R̂ + atol)` (the project's solver-error
scale, **not** a proved bound on the solver's global error) and `K` from the grid's second
difference at the best grid point. `null`, with the reason in `best_angle_note`, when the best
grid point is at an edge (no centred difference) or the grid curve is not bent downwards
there. **Observed to be pessimistic** by orders of magnitude (below): the solver's
error is smooth in the angle, so it shifts the peak far less than `ε_R` allows. The app shows
the best angle as "42.98° ± 0.002° (estimate)".

### What is tested
Every expected value comes from an independent source: closed forms written out in the tests,
the linear model's exact solution at `b = 0` (a different code path), 50-digit `decimal`
evaluations, `scipy.integrate.quad`, or a test-local DOP853 integration with its own
right-hand side and landing event (`rtol = atol = 1e-13`). Files:
`backend/tests/physics/weak_drag_reference.py` (the RS3 helper, test-side only) and
`test_weak_drag_reference.py`; `backend/tests/physics/test_quadratic_angle_sweep.py`;
`backend/tests/api/test_quadratic_angle_sweep_api.py` and
`test_quadratic_angle_sweep_limits.py`.

| Ref. | Check | Reference | Tolerance (justified in the test) | File |
|---|---|---|---|---|
| RS1 | Vacuum range at one angle: `v₀² sin 2θ/g`, a hand-worked case from 15 m, horizontal launch `v₀√(2h/g)`, exactly 0 at 90° and at 0° from the ground; matches the linear model at `b = 0` | Textbook; hand-worked; independent code path | rel 1e-14 / 1e-15; exact | `test_quadratic_angle_sweep.py` |
| RS1 | Vacuum optimum: 45° and `v₀²/g`; a hand-worked case from 15 m; lower from greater heights; slope 0 and curve bending down there (central differences); matches the linear sweep's refined optimum at `b = 0` | Closed form; independent search | rel 2ε to 1e-12; 1e-5° | `test_quadratic_angle_sweep.py` |
| RS1 | Vacuum sweeps (h = 0 with all three methods on 91 angles; h = 1, 10, 100, 1000 m with DOP853 on 31): every point to rel 1e-13, best angle to 1e-5°, best range to rel 1e-13 | Closed form | measured ≤ 5.8e-15 rel per point; best angle ≤ 1.85e-6° | `test_quadratic_angle_sweep.py` |
| RS1 | `u` in vacuum equals `2√(ε_R/4R*)` | `K = 4R*` from `sin 2θ` | rel 1e-3 | `test_quadratic_angle_sweep.py` |
| RS2 | Every grid point and every refinement run is bit-identical to an independent single 2.1 run; the sweep's evaluation count is their sum (DOP853, RK45) | The 2.1 model | exact | `test_quadratic_angle_sweep.py` |
| RS2 | Over HTTP: every point equals a separate 2.1 request at that angle | The 2.1 endpoint | exact | `test_quadratic_angle_sweep_api.py` |
| RS3 | `F(π/4)` and `F'(π/4)` follow from `F`'s definition; the float coefficients match 50-digit closed forms; `F` matches a 50-digit evaluation and quadrature of the J integrals | 50-digit `decimal`; `quad` | ≤ a few ε | `test_weak_drag_reference.py` |
| RS3 | First-order range, best angle and best range leave an `ε²` residual against the independent integration | Independent DOP853 at 1e-13 | fitted slope 2 | `test_weak_drag_reference.py` |
| RS3 | **Order test on the sweep** (ε = 5e-3, 1e-2, 2e-2, 4e-2): residuals from the first-order angle and range shrink like ε² | `weak_drag_reference.py` | slope 2 ± 0.3 (angle), 2 ± 0.1 (range); measured 1.986 and 1.983 on the 11 angles the test uses (1.983 and 1.983 on 91) | `test_quadratic_angle_sweep.py` |
| RS3 | **Wrong-coupling mutant** (`−κ|vx|vx`, `−κ|vy|vy`) fails the order test | Mutation | slopes < 1.5; measured 1.010 and 1.047 | `test_quadratic_angle_sweep.py` |
| RS4 | Best angle and range at stronger drag (c = 0.01 kg/m with DOP853 and RK45 on 91 angles; c = 0.1, 1 kg/m and from 5 m on 31; Radau on 10) against the independent integration, its optimum polished by a least-squares cubic through 21 ranges | Independent DOP853 at 1e-13 | error ≤ u **and** ≤ 2e-5°; range rel `10·(rtol + atol/R)` | `test_quadratic_angle_sweep.py` |
| RS5 | 0° from the ground is "no flight" (no solve, all exactly 0); 0° from a height is a real flight; 90° lands at exactly 0 and is checked against the exact vertical flight by its 2.1 run | Exact | exact | `test_quadratic_angle_sweep.py` |
| RS5 | Best angle falls as drag grows, from the ground, at 8 drag values from 0 to 1 kg/m (**observed**, labelled so) | Physical property | strict ordering | `test_quadratic_angle_sweep.py` |
| RS6 | Every 2.1 check passes in every run of the RS1 sweeps from the ground and the RS4 sweeps (10 sweeps, all methods) | The 2.1 per-run checks | as 2.1 | `test_quadratic_angle_sweep.py` |
| — | Aggregated checks report the worst run and its angle (recomputed from single runs); a planted failing run fails its aggregate; the mutant fails energy and invariant | Independent single runs; mutation | exact | `test_quadratic_angle_sweep.py` |
| — | Edge: best grid point at 0° (v₀ = 10 m/s from 1e5 m) gives `u = null` with the reason, 0 interior peaks, and Brent still finds the closed-form optimum | Closed form | 1e-5°; rel 1e-13 | `test_quadratic_angle_sweep.py` (the null `u` and its reason also over HTTP, in `test_quadratic_angle_sweep_api.py`) |
| — | Peak count 1 on a real curve; a planted two-peak force is flagged (not passed); the grid point is kept when it beats the refinement (Brent replaced by a stand-in) | Construction | exact | `test_quadratic_angle_sweep.py` |
| — | The stiffness guard refuses an explicit method **before any solve** and names the worst angle; the budget refuses between runs, deterministically, with the same message twice; the default sweep fits the budget with both explicit methods | Construction; independent single-run counts | exact | `test_quadratic_angle_sweep.py` |
| API | Complete labelled response; drag lowers the best angle and range; `c v_t² = mg`; vacuum from the ground and from a height; launch angle ignored in results and hash; NaN/±Infinity and invalid inputs rejected; identical inputs give identical hashes; one tolerance rule per stored field, each replaying `identical`; the best-angle rule is `max(1e-5°, u)`; the value rules survive emulated last-bit differences (4 cases) | Closed forms; contract | as stated | `test_quadratic_angle_sweep_api.py` |
| Limits | The 2.1 rules checked at the smallest flown angle (prefix "at the sweep's smallest angle …°"), worked by hand at their boundaries; **corners** of (mass, speed, `c` = 0 or largest, `g`, height) × three methods × tightest and loosest tolerances on 10 angles: a result or an explained 422, never a 500, each under 25 s, the budget refusal exercised | Contract | as stated | `test_quadratic_angle_sweep_limits.py` |

**Registry and reproducibility:** a case appended to `tests/api/test_registry.py` (RK45,
`c = 0.02 kg/m`, h = 2 m, 31 angles), so the registry, replay, recompute and golden-digest
tests pick it up; one golden entry appended to `tests/api/golden_runs.json`, the existing
entries unchanged; two headline cases in `test_experiment_log.py`. Frontend: Vitest for the
panel, export, compare and overlay, and Playwright (`e2e/quadratic.spec.ts`, two cases in
`e2e/stored-fields.spec.ts`).

### Per-run checks shown in the app
One row per 2.1 check id, **aggregated over every run of the sweep**: passed only if every
run passed; value and threshold from the run with the largest value/threshold (thresholds
differ per angle), and the note names that angle, the number of runs and those where the check
was unavailable (for example the invariant at 90°). Two of the sweep's own: **interior peaks
on the grid** (expected 1, observed in every case measured; more than 1 is shown as not passed,
because Brent searches only next to the best grid point and may have found a local maximum),
and **runs and solver evaluations** against the budget (informational).

### Observed accuracy and cost (one machine)
Intel Xeon @ 2.10 GHz, linux-x86_64, Python 3.12.3, NumPy 2.5.4, SciPy 1.18.1. Observed, not
guaranteed for other inputs or machines.

- **Best angle against the independent reference** (default tolerances `rtol = atol = 1e-10`,
  v₀ = 20 m/s): 1.2e-7° to 3.4e-6° on the six cases measured in slice 2 (all on 91 angles; the
  largest RK45 at c = 0.1 kg/m), 2.0e-8° to 8.5e-7° on the seven cases now in the tests; the
  best range within 1.5e-11 relative. `u` in the seven tested cases was 2.0e-3° to 3.0e-3°
  (recomputed 2026-10-29), so at least ~2300 times the observed error in each of those seven.
- **Vacuum:** every point within 5.8e-15 relative of the closed form; the best angle within
  1.85e-6° (Brent's stall on a flat top; the plan estimated 7e-7°).
- **Weak drag:** the sweep's residuals from the first-order formula shrink like ε² (fitted
  slopes 1.983 and 1.983); at the 2.1 defaults (ε = 0.41) the first-order angle is 42.55°
  against 42.98° computed: 0.43° off, so ε = 0.41 is not "weak".
- **Best angle against drag** (planning scratch with the independent integration, v₀ = 20 m/s,
  0.5° grid then Brent, 10 values of ε from 1e-3 to 1e3): one interior peak in all 30 cases;
  from the ground 44.994° → 40.98° → 20.34° at ε = 1e-3 → 1 → 1e3, falling throughout; from
  h = 5v₀²/g nearly flat between ε = 1 and 3 (12.549° → 12.527°).
- **Default sweeps, 91 angles, measured 2026-10-29** (a scratch script calling
  `run_angle_sweep`; v₀ = 20 m/s, m = 1 kg, h = 0, default tolerances):

| c (kg/m) | Method | Best angle | Best range (m) | u (estimate) | Runs | RHS evaluations | Wall time |
|---|---|---|---|---|---|---|---|
| 0 | DOP853 | 45.000001° | 40.788649 | 1.83e-3° | 109 | 6 518 | 0.19 s |
| 0 | RK45 | 45.000000° | 40.788649 | 1.83e-3° | 96 | 2 790 | 0.14 s |
| 0 | Radau | 45.000000° | 40.788649 | 1.83e-3° | 96 | 3 503 | 0.45 s |
| 0.01 | DOP853 | 42.975833° | 31.399867 | 1.96e-3° | 98 | 16 675 | 0.29 s |
| 0.01 | RK45 | 42.975832° | 31.399867 | 1.96e-3° | 98 | 22 876 | 0.45 s |
| 0.01 | Radau | 42.975834° | 31.399867 | 1.96e-3° | 100 | 189 011 | 5.63 s |

  (Wall time includes a single process's warm-up; one run each.)

### Input limits and the work budget
- **Inputs:** the 2.1 parameters and solver settings with the 2.1 field bounds; `n_angles`
  10 to 361. The request is valid if and only if a 2.1 request with the same parameters and
  solver is valid **at the sweep's smallest flown angle** (0° from a height, else the first
  grid step 90°/(n − 1)); refusals say where they were checked. Why that suffices: the
  drag-rate and atol rules do not depend on the angle, and the drag-free flight time grows
  with it. From the ground, Brent can fly angles below the first grid step (seen at
  v₀/v_t = 1e5 on 10 angles: a refinement run at 4.7°); there the 1 µs rule still holds,
  because a sub-microsecond flight at θ ≥ 1° forces ε ≤ 0.29 by the drag-rate rule, i.e. weak
  drag with its best angle near 45° (that last step **observed**: the lowest best angle from
  the ground at the strongest drag allowed was 9.6°). The request's own launch angle is
  ignored (and not hashed).
- **Stiffness guard:** before any solve, the 2.1 drag-time bound is computed at every grid
  angle, and an explicit method is refused (422) if any exceeds 1e4, naming the worst angle;
  refinement angles are guarded again inside each run.
- **Work budget: 3e5 right-hand-side evaluations** over the whole sweep, a server constant
  (not a request field), checked after each run, so at most one run in progress overshoots.
  Counted in evaluations, not seconds, because a count is reproducible on one machine and a
  timeout depends on load. **Justification (measured, 540 sweeps of 91 angles; grid in the
  comment at `MAX_SWEEP_RHS_EVALUATIONS`):** the browser reaches the API through the Next.js
  proxy, which gives up after 30 s by default; at 3e5 the slowest refusals took 11.4 s (Radau,
  rtol = 1e-13), so a machine about 2× slower still answers in time, while 5e5 took 19.4 s.
  3e5 admits every sweep at the 2.1 defaults with every method.

### Replay tolerances
Declared in `_quadratic_sweep_tolerances` (`api/routes/physics.py`), one rule per stored field
(tested), with `rtol' = max(rtol, 1e-10)` as in 2.1. Derived or checked by last-bit
emulation (each drag evaluation × (1 ± 1 or 2 ulp); 892 reruns of 223 sweeps, v₀ ∈ {1, 10,
20, 300} m/s, c from 0 to 1 kg/m, h from 0 to 1e5 m, all methods, rtol 1e-13 to 1e-6, 10 to
361 angles).

| Field | Rule | Reason | Largest fraction used in the emulation |
|---|---|---|---|
| `best_range` | `10·(rtol'·|x| + atol)` | the 2.1 solver rule; an angle error of 1e-5° changes a flat-top range only by ~1e-14 relative | 0.0023 |
| `best_angle_deg` | absolute `max(1e-5°, u)` (1e-5° when `u` is null) | the run's own estimate, floored by the linear sweep's rule for Brent's stall | 0.08 |
| `best_angle_uncertainty_deg` | relative `(rtol'·R + atol)·u²/(2(rtol·R + atol)Δ²)` (u, Δ in rad); `null` must stay `null` | `u` comes from a second difference `d₂`; each range moving by `dR` moves `d₂` by ≤ 4dR and `u` by ≤ 2dR/|d₂| relative, with |d₂| recovered from `u` | 0.0025 (3.4e-6 relative); the best grid point never moved |
| `vacuum_best_*`, `terminal_speed` | 1e-12 relative; `null` stays `null` | closed forms | — |
| `n_rhs_evaluations` | exact | a count: a different step sequence is a different computation | changed in 479 of 892 reruns (see limitations) |

### Known limitations
- **Every limitation of the 2.1 model applies at every angle** (constant `C_d`, no spin, lift,
  wind or buoyancy; no exact 2-D reference; empirical per-run thresholds).
- **Exact evaluation counts across CPUs.** `n_rhs_evaluations` is replayed exactly and sums
  ~100 runs: in the emulation it changed in **479 of 892** reruns, so a replay on another CPU
  will often report `differs` on that count alone. For the same reason, a sweep very near the
  budget could be admitted on one machine and refused on another.
- **No rate limit or concurrency cap** (slice 3 security review). One sweep can hold a worker
  for ~11 s, so a burst of requests would slow every request. Not changed (no authentication or
  new services in scope); a deployment decision for the author.
- **Radau at 91 angles is often refused.** In the budget measurement Radau completed 30 of 60
  cases at the default tolerances and 12 of 60 at (1e-13, 1e-14); at the 2.1 defaults it is
  admitted (1.9e5 evaluations, ~6 s). Use fewer angles, a looser tolerance, or an explicit
  method where the guard allows.
- **`u` is an estimate, not a bound,** and pessimistic by orders of magnitude; the error scale
  `10·(rtol·R + atol)` is a convention, not a proved bound.
- **Local maxima.** Brent searches only next to the best grid point; one interior peak was
  observed in every case measured, which is evidence, not a proof. The peak-count check makes
  a second peak visible; it does not fix it.
- **Peak count with exact ties.** A peak is a grid point *strictly* above both neighbours, so
  a flat top made of two exactly equal grid ranges counts 0 peaks, and the check's note then
  suggests the best point is at an edge, although the curve has one interior peak.
- **"Falls as drag grows" is observed only** (from the ground on measured grids; nearly flat
  between ε = 1 and 3 at large heights), and "below 45°" is proved only to first order in ε.
- **The RS3 formula is not checked against the literature,** and its `O(ε²)` remainder is not
  bounded.
- **UI:** "Maximum range" has no "(numerical)" tag in the shared sweep panel (on either page);
  the sweep's notes appear twice under Validation. A sweep shows "Sweeping…" with no progress.
- About 25 lines of grid-and-Brent logic are duplicated from `angle_sweep.py` until roadmap
  2.5 (generic sweeps).

---

## `physics.oscillator` (roadmap 2.3, in progress): exact solution (slice 1), numerical solve and checks (slice 2)

Plan and decisions: `docs/plans/ROADMAP_2_3_PLAN.md` (D1-D17, grilling record G1-G4 and the
slice-1 amendments). The model is `m ẍ + b ẋ + k x = F₀ cos ωt`. Slice 1 is the **exact
solution** (`backend/src/simforge/physics/oscillator/analytical.py`, pure); slice 2 the
**numerical solve** checked against it (`numerical.py`, `model.py`, `schemas.py`; see the
slice 2 section below). No endpoint or page exists yet.

### What is exact, and how it is evaluated
- **Proved (closed forms):** the steady state A, δ; the transient in one unified form for
  under-, critically and over-damped motion; the undamped driven "beat" form (exact at ω = ω₀,
  where the motion grows linearly); the amplitude peak ω_r and A_max (only when ζ < 1/√2); the
  half-power width 2γ of the power resonance curve (so Q = ω₀/Δω exactly); the free-decay ratio
  e^{−γT_d} per period. The IB's Q ≈ 2π × energy stored / energy lost per cycle is approximate
  and is labelled so wherever it appears.
- **Evaluated in floating point, with three traps avoided:** (i) the textbook 0/0 at critical
  damping (a sinc keeps one formula continuous through ζ = 1); (ii) overflow of e^{−γt}cosh βt
  for heavy damping (a two-exponential form with the slow rate written ω₀²/(γ + β), not γ − β);
  (iii) the near-cancellation of two huge terms when undamped driving is close to resonance (the
  beat form). The regime label is exact: q = ω₀² − γ², the detuning and ζ come from exact
  rational arithmetic on the float inputs, so "critically damped" means exactly b² = 4mk.
- **The scale X** (author's decision, 2026-11-03): X = √(x₀² + (v₀/ω₀)²) + D is a **proved
  upper bound** on |x(t)| over the run, from the inputs only: the free part never gains energy,
  and D is the smallest of six proved caps on the motion driven from rest (f·T²/2; a damped
  Duhamel cap; f/ω₀² and a creep cap when q ≤ 0; f/ω₀²·coth(πγ/2ω_d) when q > 0; the undamped
  beat or linear-growth cap; A plus a transient bound). Scan of 6000 adversarial cases (review):
  no violation; the motion reaches 0.58-1.0 of X in the tests.

### Limits introduced by this slice (measured, not assumed)
- **Q ≤ 1e4 when b > 0** (author's decision A, reversing G3). Near resonance the exact formula
  subtracts two terms of size A, so its rounding error relative to the motion actually reached
  grows like ε·Q. Measured against a 90-digit reference: 4.6e-12 at Q = 1e4 (1000 cycles), while
  extreme light damping gave nonsense (b = 1e-300: 1.6e290 m instead of 2.4e6 m). b = 0 is
  allowed: its beat form does not subtract.
- **Minimum duration max(ω₀, ω, γ)·T ≥ 1** (to be enforced at the API in slice 3). Below it the
  same subtraction meets a tiny motion (≈ f·t²/2): measured 1.4e-8 of X at 1e-3 of the edge,
  ≤ 1.5e-14 of X at the edge except Q = 1e4 at resonance (5.8e-12, the Q term).
- **Error model** (measured, 90-digit reference): error ≈ c·ε·(Q + ω₀T + A/X + 1)·X with
  c ≤ 1.5; tests assert c = 4. Worst state error with Q ≤ 100: 8.95e-15 of X.

### What is tested (`backend/tests/physics/test_oscillator_analytical.py`; 317 tests)
- **Independent references:** a 90-digit `decimal` evaluation of the textbook branch formulas
  (`tests/physics/oscillator_reference.py`, own series for sin, cos and π, no shared code), a
  tight DOP853 integration with its own right-hand side, Gauss-Legendre quadrature of the energy
  balance, and hand-derived closed values.
- **Identities:** the ODE residual and initial conditions; successive maxima T_d apart with
  ratio e^{−γT_d}; half-power width 2γ; the steady-state power identity ½F₀ωA sin δ = ½bω²A²;
  energy conservation when b = F₀ = 0; continuity across ζ = 1, as b → 0 and through ω = ω₀
  with b = 0; each of traps (i)-(iii); every cap of X and |x| ≤ X.
- **Mutation testing** (scratch, not in the repository): 22 planted bugs, all caught, including
  γ − β for the slow rate, float arithmetic for q, a halved cap and a missing finiteness check.

### Slice 2: the numerical solve and its per-run checks
- **What is solved (numerical):** SciPy `solve_ivp` (RK45, DOP853 or Radau) on the
  dimensionless equation, τ = ω₀t, ξ = x/X, η = v/(ω₀X) (velocity scale V = ω₀X, the author's
  decision of 2026-11-09), with the damping work integrated from b·v² and the drive work from
  F₀cos(ωt)·v, never from the force. So `atol` is a fraction of X (and of V, and of kX² for the
  works) at every scale. Maxima of x come from an event on v = 0 (the start is never one).
- **Per-run checks** (each a measured threshold, below): displacement error max|x − x_exact|/X
  and velocity error max|v − v_exact|/(ω₀X) at the step nodes against the exact solution;
  the energy balance KE + PE + W_damp − W_drive = E₀ (exact for the true motion) /kX²; for a
  free underdamped run, the time between the first two maxima against T_d and their ratio
  against e^{−γT_d} (both exact identities, OR4); informational: the transient left at the end
  as a fraction of A (exact, evaluated as the free motion it is, not as x − x_p), and the cost.
  A threshold above 1 is labelled uninformative (it cannot fail within the scale).
- **Stiffness guard:** RK45 and DOP853 are refused before any solve when the fastest
  eigenvalue times the duration, (γ + β)T overdamped and ω₀T otherwise, exceeds 1e4.
- **Thresholds, measured** (one x86_64 VM, Python 3.12.3, NumPy 2.5.4, SciPy 1.18.1; 1608 runs
  inside the limits: the 113-case corner grid of 3 methods × 4 tolerance pairs × 4 regimes ×
  free/driven plus the Risks corners, 55 runs of 100 cycles, 840 free decays with ζ from 0.01
  to 0.99, 600 seeded random runs with ζ 0 to 1e3 and ω/ω₀ 0 to 100). Form:
  `F (rtol + atol)(1 + cycles) + 1e-9`, F the smallest 1-2-5 value at least 10× the worst
  need. F = 50 (displacement), 500 (velocity), 2e4 (energy), 1e3 (period), 20 (ratio); worst
  value / threshold 0.10, 0.064, 0.067, 0.077 and 0.089 on the 1608 measured runs. The review then found one unmeasured corner (DOP853, tightest pair, undamped, from rest, 500 cycles, ω ≈ 100ω₀) where the displacement value / threshold reached 0.215 (margin about 4.6×, not 10×): there the 1e-9 floor is set by the solver's own rounding, not the exact solution's. To be measured and the floor re-justified before slice 3. The cycles term is measured, not
  assumed: displacement error/(rtol + atol), undamped, default pair, was 75 at 100 cycles and
  747 at 1000 (DOP853), 182 and 1820 (RK45). The floor 1e-9 is ≥ 100× the exact solution's
  own worst error (5.8e-12 of X).
- **The energy factor is set by fast drives.** At ω = 100ω₀ the speed reaches 50 V, so the
  energy in motion is ~1250 kX² and a relative error of ~1e-9 is ~1e-6 kX² (the grid's RK45
  corner was 0.994 of the provisional threshold). F = 2e4 covers it, but is ~800× loose for
  runs whose speed stays below V. Normalising by the energy in motion instead is an open
  question for the author.
- **Free-decay checks need a resolvable second maximum** (x₂ ≥ 1e-3 X): near critical
  damping the motion has decayed to nothing by then, and the located time is set by the
  tolerance (a correct solve gave 1e9 × (rtol + atol) at ζ = 0.9 without this rule).
- **N_max = 500 cycles** (D6 said 1000, provisional): at the default settings (DOP853,
  rtol = atol = 1e-10) 500 cycles took 0.8-1.4 s and 1000 cycles 1.7-2.5 s (D6: ≤ 2 s).
  Other settings are slower at 500 cycles: DOP853 at the tightest pair 2.4-3.4 s, RK45 2.4-4.5
  s, Radau 4.9-8.2 s (middle pair) and 36-78 s (default pair, above the 30 s proxy limit). A
  cycle limit alone cannot bound Radau's time; that rule is an open decision for slice 3.
- **Tested** (`backend/tests/physics/test_oscillator_numerical.py`, 84 tests;
  `test_oscillator_model.py`, 166 tests; constants in `oscillator_thresholds.py`): agreement
  with the exact solution in every regime at the tightest pair; the error falls as the
  tolerance tightens; scaled and SI states agree to 4ε; unit invariance (m, k, b, F₀ × 1024);
  dense output at the nodes; works exactly 0 when F₀ = 0 or b = 0; a wrong damping law
  (−b·v·|v|/V) fails the energy balance and the displacement check while the true one passes;
  maxima against OR4; the corner grid; the diagnostics recomputed independently from the
  nodes; nulls when undriven, undamped or overdamped; the guard refusing before any solve and
  naming its number; the steady state and resonance curve against their formulas.

### Limitations
- Measurements are from one machine (Python 3.12, NumPy 2.5.4, SciPy 1.18.1); run times vary
  by up to ~1.5× on it.
- Inside the limits, the exact solution's worst error is at Q = 1e4 near resonance (≈ 6e-12
  of X); the checks' floor (1e-9) allows for it.
- The checks' thresholds come from 1608 runs, not a proof: the global error of an adaptive
  solver is not bounded by its tolerances.
- The energy check is loose for slow motions (see above), and the free-decay checks are absent
  when the second maximum is below 1e-3 X.
- The decay envelope is a correct bound but uninformative near critical damping; the page
  (slice 4) will show it only when it is useful.

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

Every verdict also lists any environment differences (library versions, platform, CPU model,
git commit, Python implementation). Refusals, each with its own test: unknown run (404), unknown
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
| quadratic drag | `numerical.*` values; counts and settings; `terminal_speed`, `vacuum.*`, bounds; energy residual; invariant residual | `10·(rtol·|x| + atol)`; exact; 1e-12 rel; abs `10·(rtol + atol/v₀)`; abs `10·(rtol + atol/min(vx₀, v_t))` (rtol floored at 1e-10 throughout) | as the projectile; the residuals use the per-run checks' own scales; below rtol = 1e-10 rounding sets the accuracy (details in the quadratic-drag section) |
| quadratic angle sweep | best range; best angle; `u`; vacuum values, terminal speed; `n_rhs_evaluations` | `10·(rtol'·|x| + atol)`; abs `max(1e-5°, u)`; relative, derived from how `u` is computed (`null` stays `null`); 1e-12 rel; exact | the solver rule; the run's own estimate floored by Brent's stall; checked by last-bit emulation (892 reruns; details in the quadratic angle-sweep section) |
| integrators | horizon; orders; fit points; theoretical order | 1e-12 rel; 1e-6 rel; exact; exact | fits use only points far above rounding |
| integrators | finest max position error | 1e-9 m absolute | rounding-dominated at the finest RK4 step; ≲5e-10 m over 5e4 steps |
| angle sweep | best angle; best range; vacuum values | 1e-5° abs; 1e-10 rel; 1e-12 rel | Brent's ~1e-6° tolerance at a flat maximum |
| Solow | k\*(s₀), k\*(s₁) | `2 × 8u·(1/(1−α)+2)` relative | twice the empirical k\* bound above |
| Solow | final capital | `2 × 64u/(1−ρ)` relative | twice the empirical path bound above |
| Solow | golden-rule rate; half-life | exact; 1e-12 rel | a copy of α; a closed form |
| dataset profile | every field | exact | counts and labels |

**What is and is not established.** Measured: on one machine, every model's runs replay
**bit-identically** (a test runs every registry case: the six cases before roadmap 2.1
locally and in CI; the seventh, quadratic drag, locally in the 2.1 slice checks; the eighth, the quadratic angle sweep, locally in the 2.2 slice checks). **Across machines they do
not**: with the same code and the same locked libraries, GitHub's CI runners gave different
output digests for the four floating-point models (the dataset profile, all counts, matched).
Locally, forcing OpenBLAS (NumPy's linear-algebra library) onto other CPU-specific routines
changed the projectile and integrator digests the same way, because those routines add
numbers in a different order; the largest summary change was about 1e-15 relative
(`max_height` 4.250749496135367 → …371), far inside the declared tolerance (5e-9 m). The
sweep and Solow digests also differ in CI for a CPU-specific reason not pinned down here. On
CI's AMD EPYC 7763 (pinned on an Intel Xeon), the projectile summary agreed within its
declared tolerances; its largest change was `analytical.range` 24.751641053406477 →
…466, about 4e-16 relative.
So the tolerances are reasoned from each method's error control and the empirical rounding
bounds above; they are now checked against real cross-machine differences on every CI run
(the golden test below), but that is one other machine type, not a proof. Every run records
its CPU model so a replay can say when the processor changed.

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
`tests/api/test_golden_digests.py` (fixed inputs per model version: the pinned digest must
match, or, on a different machine, every summary value must lie within its declared tolerance,
with a warning saying only that was checked; a regression guard, not evidence of correctness) and `tests/api/test_replay.py` (every verdict, every refusal, saving and linking). Mutation
checks: ignoring the digest, a tolerance made 10¹² times looser, and dropping the replay link
each fail a test.

### Known limitations
- Replays of v1 records (before 1.4) compare only the stored summary.
- `within_tolerance` covers the summary only; time series are not stored, so not compared.
- Model versions were not bumped when PRs #8 and #9 changed some outputs (the t = 0 landing
  fix, check notes). A v1 record affected by those fixes replays as `differs`, which is true.
- Deleting runs is deferred: with no authentication, a delete endpoint would let anyone
  delete anyone's runs. To remove runs, stop the server and edit or delete the SQLite file.

## Comparison and export (roadmap 1.6)

Roadmap 1.6 adds three things that move numbers out of a run: recomputed outputs for a stored
run (`POST /api/v1/experiments/{run_id}/outputs`), CSV downloads made in the browser, and a
versioned JSON export of a run record (`GET /api/v1/experiments/{run_id}/export`). It also
adds a comparison of two runs of the same model. None of them computes anything new about
the science; what has to be established is that the numbers they show or write are the
model's numbers, unchanged.

### Recomputed series: the digest says whether they are exact
The log stores no series (ARCHITECTURE decision 5), so a stored run's curves are obtained by
computing it again from its stored inputs, with the same refusals as replay (one shared
helper). The response carries `digest_match`: **true** if the recomputation's output digest
equals the one stored with the original run, which means every output value is
bit-identical (see "Reproducibility and replay" above for why equal digests imply that);
**false** if both digests exist and differ; **null** for a v1 record with no digest. The page
shows these as "recomputed, bit-identical", "recomputed, not bit-identical (cause not checked;
usually another CPU or library version)" and "recomputed; cannot be checked". The false label
names the usual cause but does not claim it: nothing compares the environments at this
point (a replay does).

**Tested** (`backend/tests/api/test_run_outputs.py`):
- All six models (seven cases: the dataset profile both as a bundled sample and as an upload
  sent again) recompute with `digest_match` true. The expected digest is the one stored with
  the original run, recorded before the recomputation. As an independent check, the test also
  hashes the response it received with a canonical-JSON function written in the test from the
  definition (sorted keys, no spaces, finite floats), not imported from the code, and gets the
  stored digest.
- A stored digest that differs is reported as false, not hidden; a v1 record gives null.
- Recomputing saves nothing (the log has the same number of runs before and after), and a
  request to save is refused by the schema.
- Every refusal: unknown run 404, unknown model 422, changed model version 409, stored inputs
  no longer valid 422, an upload without its file 422, a different file 422 (refused before it
  is read), a file for a model that takes none 422, a domain error 422, a body that is not
  base64 422, an oversized body 413. A further test sends the same bad requests to replay and
  to recompute and requires the same status and message from both.

**Observed (2026-10-24, one machine).** Recomputing the slowest model, the integrator study at
its total-step cap (150,000 steps, summed over the three methods and all step sizes), took a
median of about **1.47 s** over 5 repeats, on an Intel Xeon 2.10 GHz cloud container. It was
timed in-process through FastAPI's test client, so it includes the HTTP layer but no network
or browser time. This is one measurement on one machine, not a bound: a slower computer, or a
busy one, will take longer. The page shows "Recomputing reference run …" while it waits.

### CSV: what is written is the number that was computed
**Guaranteed by the language specification, and tested.** Each number is written with
JavaScript's `String(x)`, which the ECMAScript specification defines as the shortest decimal
string that converts back to exactly the same double. So `0.1 + 0.2` is written
`0.30000000000000004`, not `0.3` (which would be a different double). The tests
(`frontend/src/lib/export/csv.test.ts`) check that exact output and that each of `1e-300`,
`5e-324` (the smallest positive double), `1/3`, `0.1 + 0.2`, the largest double and
`2^53 + 2` round-trips exactly through `Number(cell)` (compared with `Object.is`, which also
tells `0` from `-0`). `-0` is written `-0`, because `String(-0)` gives `"0"` and would lose the
sign. A non-finite number makes the export fail instead of writing `NaN` or `Infinity` (the
models never return one; the schemas reject them).

Also tested there: RFC 4180 quoting (a field with a comma, quote, CR or LF is quoted, quotes
doubled; CRLF line endings), `name [unit]` headers (quoted when a unit contains a comma),
`null` and the end of a shorter column as empty cells, and the formula guard below.
`frontend/src/lib/export/tables.test.ts` checks, for each model, which columns are exported,
with which units, and specific rows against the fixture's values; the dataset profile
exports per-column statistics only, never rows. `e2e/reference.spec.ts` downloads a real
Solow CSV and checks its filename and header line.

What is **not** claimed: a spreadsheet program may still display or re-save a number with
fewer digits; the guarantee is about the file as written.

**The formula guard (a safety rule, tested).** Text starting with `=`, `+`, `-`, `@`, a tab or
a carriage return gets a leading `'`, so a spreadsheet treats it as text rather than a
formula. It applies to headers too, because Quant column names come from the user's file.
Numbers are never prefixed: a negative number starts with `-`, and prefixing it would turn a
number into text. A test checks that `-3.2` stays `-3.2`.

### JSON export
`RunExport` is `{export_version: 1, exported_at, record}`. **Tested**
(`backend/tests/api/test_run_export.py`): `record` equals `GET /experiments/{run_id}`
unchanged; `exported_at` is a UTC time between the request's start and end; an unknown run is
404; the download filename contains the model id and run id only, never a run's name or note
(the record inside the file does include them, as `GET` shows them). It holds the record, not
series: a full run is reproduced by recomputing it, as above.

### The comparison: differences, not verdicts
For each stored summary value of two runs of the same model, the table shows the reference
value `a`, the new value `b`, the change `b − a`, and the **relative change**
`(b − a) / |a|`. The absolute value in the denominator keeps the sign meaning "went up" or
"went down" even when `a` is negative. When `a = 0` the relative change is **undefined** and
shown as "—": any change from 0 is infinitely large relative to 0, and `0 → 0` would be
`0/0`. It is never shown as `Infinity`. A change too large to represent (a ratio to a tiny
reference that overflows) is also shown as "—". Values are rounded to 6 significant figures
for display only; the changes are worked out from the full values. Non-numeric values (text,
booleans, null, a field present in one run only) are shown as "equal" or "changed", with no
arithmetic; `null` against a number is "changed", never treated as 0.

**Tested** (`frontend/src/lib/reference/compare.test.ts`, `components/ComparisonTable.test.tsx`):
the two formulas on hand-worked values, the reference-0 case, overflow, non-numeric rows, only
the differing inputs listed, nothing shown for two different models or a run compared with
itself. **Drift check (end-to-end):** the browser rebuilds the inputs and summary a run record
stores. `e2e/stored-fields.spec.ts` saves one real run per model (two for the dataset profile)
through the real API and requires the browser's fields to equal the stored record's exactly.
Both sides come from the same run on the same machine, so exact equality is the right test.

**Why there is no significance verdict.** The table never says that a change is "significant"
or "within tolerance". Two reasons:
- The replay tolerances (above) answer a different question: did a *recomputation of the same
  run* reproduce it, allowing for rounding on another machine? Applied to two *different*
  scenarios, "within tolerance" would only say the difference is about as small as rounding
  noise, and would read as "no real difference", which is not what was tested.
- Statistical significance needs a model of random variation (sampling, measurement noise,
  random shocks). Today's models are deterministic: the same inputs give the same numbers, so
  a difference between two runs is exactly the model's response to the changed inputs.
  Whether that response *matters* is a scientific judgement about the question being asked,
  which the table cannot make. When models with random shocks arrive (Phase 3 Monte Carlo
  runs, Phase 5-6 statistics), their uncertainty will be reported by those models, with
  their own validation.

### Limitations
- A reference with a different time grid (a projectile with a different flight time) is
  overlaid, but curves are not subtracted point by point.
- Overlays are same-model only; a reference from another model is kept but not drawn.
- Across machines, `digest_match` false is expected (see the CI findings above); the
  recomputed curves are then the current machine's, not the original's.
- A profile of an uploaded file can only be a reference in the tab that holds the file; it is
  lost on reload, because the server never stores the file.
- Assumed, not tested: Plotly's built-in PNG download is enough for chart images, and large
  responses pass the frontend proxy.
