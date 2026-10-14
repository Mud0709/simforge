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
