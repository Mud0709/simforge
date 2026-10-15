# SimForge learning guide: Milestone 0 + integrator study

A guided reading of the code as of commit `acf6251`. Line numbers refer to that commit.
Read it with the files open: each section quotes a small excerpt, then explains what the
important lines do and why.

---

## 1. Modelling projectile motion with linear drag

### The physics, in plain words
A ball is thrown. Two forces act on it: gravity pulls it down, and air resistance pushes
against its motion. *Linear* drag means the resistance is proportional to the velocity:
twice as fast, twice the drag.

```
F = m g (downward) − b v        (b in kg/s)
```

Divide by mass, and write `k = b/m` (units 1/s, a *rate*):

```
dvx/dt = −k vx            dvy/dt = −g − k vy
dx/dt  = vx               dy/dt  = vy
```

Two things are worth noticing:

- The x and y equations are **decoupled**: the horizontal motion never "sees" gravity.
- They are **linear** first-order ODEs. That is why an exact solution exists. Quadratic
  drag, `F ∝ |v| v`, couples x and y, and the exact solution disappears.

`1/k` is the **relaxation time**: after a few multiples of it, the velocity has forgotten
its initial value. `g/k` is the **terminal speed**.

### The exact solution, and the trick that keeps it accurate
`backend/src/simforge/physics/projectile/analytical.py:121-133`

```python
u = setup.k * t
ps = psi(u)
decay = np.exp(-u)
x = setup.vx0 * t * ps
y = setup.launch_height + setup.vy0 * t * ps - setup.gravity * t**2 * phi(u)
vx = setup.vx0 * decay
vy = setup.vy0 * decay - setup.gravity * t * ps
```

- `u = k t` is time measured in relaxation times, a **dimensionless** variable.
- `vx = vx0 · e^{−kt}`: the horizontal velocity decays exponentially. That's the whole
  horizontal story.
- `psi(u) = (1 − e^{−u})/u` and `phi(u) = (e^{−u} − 1 + u)/u²` are helper functions.
  As `u → 0` (no drag), `psi → 1` and `phi → ½`. The equations then become exactly
  `x = vx0·t` and `y = h + vy0·t − ½gt²`, the vacuum formulas you know.

**Why not just use the textbook formula?** The textbook writes
`y = τ(vy0 + v_t)(1 − e^{−t/τ}) − v_t·t`. With weak drag, `τ` and `v_t` are enormous, so
this subtracts two huge, nearly equal numbers. Most significant digits cancel. This is
**catastrophic cancellation**. `psi` and `phi` avoid it with `expm1` and, for small `u`,
a Taylor series (`analytical.py:105-118`):

```python
small = u < _SERIES_THRESHOLD
safe_u = np.where(small, 1.0, u)  # avoids 0/0 in the branch np.where discards
return np.where(small, _series(u, _PSI_SERIES), -np.expm1(-safe_u) / safe_u)
```

`np.where` evaluates *both* branches, so `safe_u` stops the unused branch from dividing
by zero and raising a warning. The test
`test_stable_form_avoids_catastrophic_cancellation` in
`backend/tests/physics/test_projectile_analytical.py` demonstrates the failure and the
fix against a 50-digit reference.

### Landing time
`y(T) = 0` has a closed form using the Lambert W function (`analytical.py:155-172`), but
that form loses accuracy for weak drag. So the code finds the root of the exact `y(t)`
with Brent's method instead, and the tests check the two against each other. The honest
label for the result is therefore "**exact equation, solved numerically to about 1e-15**",
not "closed-form".

---

## 2. Euler, RK4 and the specialised velocity update

All three methods turn the ODE `s' = f(t, s)` into a recipe: "from the state now, compute
the state one step `h` later".

### Forward Euler: `backend/src/simforge/numerics/fixed_step.py:42-43`
```python
def euler_step(f: RHS, t: float, y: FloatArray, h: float) -> FloatArray:
    return y + h * f(t, y)
```
It assumes the slope at the *start* of the step holds for the whole step. Its global
error is proportional to `h`, so it is **first order**.

### Classical RK4: `fixed_step.py:46-51`
```python
k1 = f(t, y)
k2 = f(t + 0.5 * h, y + 0.5 * h * k1)
k3 = f(t + 0.5 * h, y + 0.5 * h * k2)
k4 = f(t + h, y + h * k3)
return y + (h / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
```
RK4 samples the slope four times (start, two midpoint estimates, end) and takes a
weighted average with weights 1-2-2-1, the same pattern as Simpson's rule. Its error is
proportional to `h⁴`, so it is **fourth order**: halving `h` cuts the error about 16×.

Both functions are **generic**. They know nothing about projectiles and only call `f`.

### Velocity Verlet with implicit drag: `backend/src/simforge/physics/projectile/integrator_study.py:146-155`
Condensed, with comments added for this guide; the code is otherwise the same:
```python
ax, ay = -k * vx, -g - k * vy
denom = 1.0 + 0.5 * k * h
return np.array([
    x + h * vx + 0.5 * h * h * ax,                  # position: 2nd-order Taylor step
    y + h * vy + 0.5 * h * h * ay,
    (1.0 - 0.5 * k * h) * vx / denom,               # velocity: trapezoidal rule,
    ((1.0 - 0.5 * k * h) * vy - g * h) / denom,     # solved exactly for v_{n+1}
])
```
Velocity Verlet averages the acceleration at the start and the end of the step. But here
the end-of-step acceleration depends on the end-of-step *velocity*, which is the unknown.
That makes the update **implicit**. Because drag is linear, the equation can be
rearranged and solved exactly; that is where `denom = 1 + kh/2` comes from. The result is
**second order**, and stable at any step size.

| | Euler | RK4 | Verlet (this form) |
|---|---|---|---|
| Evaluations of `f` per step | 1 | 4 | specialised formula |
| Order | 1 | 4 | 2 |
| Explicit or implicit | explicit | explicit | implicit (solved exactly) |
| Generic or problem-specific | generic | generic | specific to linear drag |

**Important caveat.** Verlet is famous for *symplecticity*: it conserves energy well over
long times in frictionless systems. That property is **irrelevant here**, because drag
removes energy. Verlet appears in this study because it is a sound second-order method,
not because of its reputation.

---

## 3. Stability, convergence order and round-off

### Stability: "does a small error shrink or explode?"
Apply a method to the simplest decaying equation, `y' = −k y`. Each step multiplies `y` by
a number `R(z)`, where `z = −kh`. This `R` is the **stability function**:

| Method | `R(z)` | Stable when |
|---|---|---|
| Euler | `1 + z` | `kh ≤ 2` |
| RK4 | `1 + z + z²/2 + z³/6 + z⁴/24` | `kh ≤ 2.7853…` |
| Verlet (this form) | `(1 + z/2)/(1 − z/2)` | every `kh` |

If `|R| > 1`, every step *amplifies* the error, and after a few hundred steps the numbers
overflow. That isn't inaccuracy; it's **instability**, and making `rtol` smaller can't fix
it. Only a smaller `h` (or a different method) can.

The RK4 limit isn't typed in by hand. It's computed (`integrator_study.py:85-93`):
```python
return -float(brentq(lambda z: rk4_stability(z) - 1.0, -3.0, -2.5, xtol=1e-15))
```
Note the `- 1.0`. RK4 fails where `R = +1`, not `−1`. The first draft got this wrong, and
because the code *computes* the root, it crashed instead of silently storing a wrong number.

### Convergence order: "how fast does the error shrink?"
If error ≈ `C·hᵖ`, then `log(error) = log C + p·log h`, which is a straight line of slope
`p` on log-log axes. `backend/src/simforge/numerics/convergence.py` estimates `p` in two ways:

- `local_orders` (line 40): `log(e₁/e₂)/log(h₁/h₂)` between neighbouring step sizes. This
  shows *whether* the slope has settled.
- `fit_order` (line 57): `np.polyfit(x, y, 1)`, a least-squares line through all accepted
  points. It returns `None` with fewer than `MIN_FIT_POINTS = 3` points (line 20).

### Round-off: "the floor you can't dig below"
Computers store about 16 significant digits (`ε ≈ 2.2e-16`). Every step adds a tiny
rounding error, so with `N` steps the accumulated rounding error is very roughly
`N·ε·scale`. Once the method's true error falls below that level, shrinking `h` stops
helping and the log-log line flattens. Fitting those points would *understate* `p`.

### The fit rule that combines all three: `integrator_study.py:79-81, 254, 269-271`
```python
MAX_KH_FOR_FIT = 0.2
MAX_H_OVER_T_FOR_FIT = 1.0 / 20.0
ROUNDOFF_SAFETY = 100.0  # floor = ROUNDOFF_SAFETY * N * eps * scale
...
pos_floor = ROUNDOFF_SAFETY * n * EPS * pos_scale
...
reason = _exclusion_reason(stability, sol.diverged, kh, h / horizon)
in_pos = reason is None and errors[0] is not None and errors[0] > pos_floor
```
A run counts towards the fit only if it is **stable**, **asymptotic** (small `kh` and
`h/T`, so the leading error term dominates) and **above round-off**. This rule was written
*before* looking at results. Choosing which points to fit after seeing the data is a quiet
way of manufacturing the answer you wanted.

---

## 4. Using the analytical solution to test numerical solvers

The pattern is the same everywhere: **run the solver, evaluate the exact solution at the
same times, and measure the distance**. From `integrator_study.py:259-261`:

```python
x, y, vx, vy = analytical.state(setup, sol.t)
pos_err = np.hypot(sol.y[:, 0] - x, sol.y[:, 1] - y)
vel_err = np.hypot(sol.y[:, 2] - vx, sol.y[:, 3] - vy)
```
`np.hypot(dx, dy)` is `√(dx² + dy²)`, the Euclidean distance in metres, at every grid node.

This only works if **the reference is trustworthy**, so the reference is tested first,
against *independent* sources (`backend/tests/physics/test_projectile_analytical.py`):
textbook vacuum formulas, a 50-digit `decimal` evaluation, the Lambert-W closed form, the
terminal-velocity limit, and a check that the formulas actually satisfy the ODE.

The strongest single test of the integrators doesn't use the continuous solution at all.
It uses each method's **exact discrete solution**
(`backend/tests/physics/test_projectile_integrators.py:56-67`):

```python
sol = study.integrate(s, method, kh / s.k, n)
expected = s.vx0 * study.amplification_factor(method, kh) ** np.arange(n + 1)
np.testing.assert_allclose(sol.y[:, 2], expected, rtol=1e-12, atol=1e-300)
```
Because `vx' = −k vx` is linear, *any* of these methods must produce exactly
`vx_n = vx0 · R(−kh)ⁿ`. That pins the implementation down to about 12 digits, including
for unstable step sizes, where a "the error is small" test would tell you nothing.

Two traps the tests guard against:
- **Too-easy references.** In a vacuum the trajectory is a parabola, and RK4 and Verlet
  reproduce it *exactly*. A vacuum test would "pass" a solver of any order. That's why the
  study requires `b > 0` (`integrator_schemas.py:40-46`).
- **Non-independent evidence.** Euler and RK4 conserve `v + k·r + g·t·ŷ`, so their velocity
  error is *exactly* `k ×` their position error. Their velocity order is the position order
  again, not a second confirmation.

---

## 5. How the layers connect

```
Browser form ──► frontend/src/lib/api/client.ts ──POST──► /api/v1/physics/projectile/integrators
 (IntegratorLab.tsx)      runIntegratorStudy()              backend/src/simforge/api/routes/physics.py
                                                                    │ validates IntegratorStudyRequest
                                                                    ▼  (Pydantic, integrator_schemas.py)
                                          integrator_model.run()  ── orchestration + step limits
                                                                    ▼
                                          integrator_study.run_study() ── pure NumPy engine
                                                ├─ numerics/fixed_step.py  (Euler, RK4)
                                                ├─ numerics/convergence.py (fits)
                                                └─ analytical.state()      (reference)
                                                                    ▼
                    _record_run() → SQLite experiment log; response → IntegratorResults.tsx (Plotly)
```

| Layer | File | Job | May import |
|---|---|---|---|
| Schema | `physics/projectile/integrator_schemas.py` | the *contract*: types, bounds, units, validation | Pydantic |
| Engine | `physics/projectile/integrator_study.py`, `numerics/*` | the science | NumPy and SciPy only |
| Orchestration | `physics/projectile/integrator_model.py` | engine dataclasses → schemas; refuses runs that are too expensive | schema + engine |
| HTTP | `api/routes/physics.py` | thread pool, error codes, metadata, persistence | everything above |
| Frontend | `frontend/src/components/Integrator*.tsx` | form, plots, tables | generated types |

**Validation happens at the boundary, once, strictly.** Every schema inherits from this
class (`backend/src/simforge/core/schemas.py:18-19`):
```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, frozen=True)
```
`extra="forbid"` turns a typo into an error. `allow_inf_nan=False` rejects `NaN`, which
Python's JSON parser would otherwise accept. `frozen=True` makes validated input immutable.

**One source of truth for the contract.** `backend/scripts/export_openapi.py` writes the
schema to `frontend/src/lib/api/openapi.json`. Then `npm run gen:api` generates
`schema.d.ts` from it, and the frontend even reads its *form limits* from the same file
(`frontend/src/lib/integrators/steps.ts:7`):
```ts
const dtSchema = openapi.components.schemas.IntegratorStudyRequest.properties.dt_values;
```
If a backend bound changes, the frontend picks it up, and CI's `api-contract` job fails if
someone forgets to regenerate.

**Tests mirror the layers:** `tests/numerics/` (generic maths), `tests/physics/` (science),
`tests/api/` (contract and HTTP), `frontend/src/**/*.test.ts(x)` (UI logic with `fetch`
mocked), and `frontend/e2e/` (the whole stack in a real browser).

---

## Exercises

Try each one before opening the hints.

### Exercise 1: Euler's stable-but-strange zone (pen and paper, then verify)
Using `vx_{n+1} = (1 − kh)·vx_n`:
(a) For which `kh` does `vx_n` decay *smoothly*? (b) For which does it decay while
**flipping sign every step**? (c) For which does it blow up? Then check part (b) in the
app by entering two time steps with `b = 1`, and read the `R(−kh)` column.

<details><summary>Hint</summary>
Look at the sign and size of `1 − kh`. Something different happens at `kh = 1` that the
stability limit (`kh = 2`) doesn't mention. Ask yourself whether "stable" means
"physically sensible".
</details>

### Exercise 2: derive Euler's exact error in a vacuum
With `b = 0`, Euler gives `vy_n = vy0 − g·n·h` and `y_{n+1} = y_n + h·vy_n`. Find a
closed form for `y_n − y_exact(t_n)` as a function of `g`, `h` and `t_n`. Is the
numerical ball too high or too low? Confirm your formula with
`study.integrate(setup_with_b0, "euler", h, n)` in `uv run python`. (Note: `run_study`
rejects `b = 0`, but `integrate` does not.)

<details><summary>Hint</summary>
`y_n` contains the sum `h·(vy0 + (vy0 − gh) + … )`. You'll need the sum of
`0 + 1 + … + (n−1)`. The answer is proportional to `h`, which explains why Euler is first
order even here.
</details>

### Exercise 3: predict, then test, the halving ratios
Before running anything, predict by what factor each method's error shrinks when `h` is
halved. Then open "All runs" in the UI and check consecutive rows. Finally, explain why
RK4's two *finest* rows don't follow your prediction as cleanly, and which part of the fit
rule handles that.

<details><summary>Hint</summary>
The factor is `2ᵖ`. For the second part, compare the error column with
`position_roundoff_floor` in the API response, and reread Section 3 on round-off.
</details>

### Exercise 4 (stretch): write a failing test first
In `backend/tests/numerics/test_fixed_step.py`, add a test showing that RK4 is **not**
exact for `y' = t⁴`, even though it is exact for cubics. Predict the error after one step
from `t = 0` before you run it.

<details><summary>Hint</summary>
Simpson's rule integrates `t⁴` with a small, known error. Integrate `t⁴` exactly over
`[0, h]` and compare with Simpson's weights 1-4-1 (RK4's 1-2-2-1 with the two midpoint
evaluations combined).
</details>

---

## Verified facts and assumptions

**Verified in this session by running code or reading git:**
- Commit `b629afd` is the root commit (foundation); `acf6251` is its only child
  (integrator study).
- 167 backend tests, 46 frontend unit tests and 4 E2E tests passed locally at `acf6251`.
- Fitted orders on the default case are 1.009, 4.027 and 2.000. The finest local orders
  are within 0.011 of theory in all three test cases.
- RK4's real stability limit is kh = 2.785293563…, and the minimum of `R` on the stable
  interval is about 0.2704.
- Euler's vertical error in a vacuum equals `+g·h·t/2` to about 1e-15 (computed while
  writing Exercise 2).

**Assumptions and judgement calls (reasonable, but not proven):**
- The fit thresholds (`kh ≤ 0.2`, `h ≤ T/20`, ×100 round-off margin) are conventions, not
  derived limits.
- The round-off floor `N·ε·scale` is a heuristic upper bound. Real accumulation is often
  closer to `√N·ε·scale`.
- Convergence behaviour seen on this *linear* problem is assumed, not shown, to carry over
  to nonlinear problems such as quadratic drag.
- Linear drag describes small, slow objects. For everyday balls this is a modelling
  assumption that is known to be inaccurate.
