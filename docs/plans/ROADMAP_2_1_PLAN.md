# Roadmap 2.1 plan: quadratic drag (decided by default)

Written by the autopilot on 2026-10-25 (planning subagent). **Decided by the autopilot by
default on 2026-10-25**: the author delegated Phase 2's design questions ("agree to
defaults"), so the autopilot ran `grilling` on itself and accepted its own recommendation for
every question below (D1-D12). Every decision is **reversible**, and the author reviews it;
nothing is built until this plan has been read. PR #12 (roadmap 1.6) is merged (`origin/main`
is at `82ca0b2`), so building can start on a new branch and PR.

**The fact that drives most choices:** the integrator study and the angle sweep reuse the
linear model's `ProjectileParameters` (`physics/projectile/integrator_schemas.py:26`,
`physics/projectile/schemas.py:170-173`), and all three models hash and store
`parameters` as dumped (`api/routes/physics.py:114, 217, 287-290`). Adding a field such as
`drag_law` to that schema would add it to every rebuilt request, so every stored run of
those three models would hash differently and replay would refuse it with 409
(`api/runs.py:126`). It would also change three models' responses and digests, so all three
would need a version bump and new golden runs. Quadratic drag is therefore a **new model
with its own parameters**, and the existing physics models are left exactly as they are.

## What 2.1 builds
A second projectile page where air resistance grows with the **square** of the speed:
F = −c|v|v. This is the drag a thrown ball really feels, and unlike linear drag it has **no
exact formula** for a 2-D flight. So the computer has to solve it numerically, and SimForge
has to show the numbers can be trusted without an exact answer to compare with. It does that
in five ways: (1) a ball thrown straight up and falling back *does* have an exact solution
(`tan` on the way up, `tanh` on the way down), so vertical throws are checked against it;
(2) as c → 0 the result must turn into the familiar drag-free formulas; (3) a long fall must
level off at the terminal speed √(mg/c), where drag balances weight; (4) kinetic energy plus
potential energy plus the work done against drag must stay constant; and (5) a lesser-known
conserved quantity of the 2-D motion (the "hodograph invariant", derived below) must stay
constant. The page shows the trajectory next to the drag-free one, speed against time
levelling off at the terminal speed, and the energy budget. Runs save, replay, recompute,
export and compare like every other model.

## Design tree and rounds (self-grilled)
- **Round 1** (no prerequisites): D1 formulation and parameters; D2 new model or an option on
  the existing one; D5 which references validate it.
- **Round 2** (after D1, D2, D5): D3 solver and landing event; D4 integration cap and
  stiffness guard (needs D1's parameters and D5's bounds); D6 input limits; D7 response,
  summary and charts.
- **Round 3** (after D2, D7): D8 replay tolerances and golden run; D9 UI; D10 the 1.6
  export/compare/overlay wiring; D11 learning-guide scope; D12 seams for `tdd`.

Each decision below lists the options, the **default taken** (in bold) and why.

## Decisions
- **D1. Formulation.** F = −c|v|v, so `dvx/dt = −κ|v|vx`, `dvy/dt = −g − κ|v|vy` with
  κ = c/m. Inputs: (a) c in kg/m plus mass; (b) ρ, C_d and area, c = ½ρC_dA; (c) terminal
  speed as the input. **(a)**, mirroring the linear model's `b` plus mass, with the terminal
  speed √(mg/c) shown as a derived result and c = ½ρC_dA explained in the guide and the
  field description. The field is named **`drag_constant`**, not `drag_coefficient`:
  "drag coefficient" usually means the dimensionless C_d, and the linear model already uses
  `drag_coefficient` for b in kg/s (`schemas.py:35-40`). c = 0 is allowed and means vacuum,
  as b = 0 does. Gravity, speed, angle, height and mass keep the linear model's bounds.
- **D2. New model, or a drag-law option on the existing one?** (a) `drag_law` field on
  `ProjectileParameters`; (b) a new model. **(b)**: `physics.projectile.quadratic_drag`
  v1.0.0, "Projectile motion with quadratic drag", endpoint
  `POST /api/v1/physics/projectile/quadratic-drag/simulate`. (a) would make every stored
  projectile, integrator-study and sweep run unreplayable (see the driving fact above) and
  force three version bumps. Files follow the precedent of the integrator study and the
  sweep, which live as separate modules in `physics/projectile/`:
  `quadratic_reference.py` (closed forms, invariant, bounds), `quadratic_numerical.py`
  (the ODE solve), `quadratic_model.py` (orchestration, `MODEL_INFO`, `UNITS`,
  `ASSUMPTIONS`), `quadratic_schemas.py` (reuses `SolverSettings` and `NumericalResult`
  unchanged). The existing models' golden digests must stay unchanged, which the golden test
  checks.
- **D3. Solver and landing event.** (a) generalise the existing `integrate()` to take any
  force law; (b) a separate integrator for the new RHS, copying the event logic.
  **(b)**: SciPy `solve_ivp` with the same `SolverSettings` (RK45, DOP853 default, Radau;
  rtol = atol = 1e-10 by default), state `[x, y, vx, vy, W]`, a terminal landing event with
  `direction = −1` and the "launch instant counts as above ground" guard
  (`numerical.py:73-82`), an apex event on vy, dense output. (a) would edit the linear
  model's code path, risking its digests for no gain. The roughly 40 duplicated lines are
  recorded as a risk, and extracting them is left to 2.4 (the methods workbench "for any
  time-stepping model" is where a shared stepping and event layer belongs). Landing
  location: SciPy refines events with `brentq(xtol = rtol = 4·EPS)` on the dense output
  (verified in the installed SciPy, `scipy/integrate/_ivp/ivp.py:75-77`), so the landing
  error is the interpolant's error, about the solver tolerance.
- **D4. Integration cap and stiffness guard.** The linear model caps integration at
  2 × the exact flight time and refuses stiff runs from the exact k·T (`model.py:169-186`);
  quadratic drag has no exact 2-D flight time. Options: (a) a fixed large cap; (b) a
  **proved upper bound** on the flight time (R7 below); (c) no guard. **(b)**: cap
  `t_max = T_bound`, and refuse (422, with the reason) when the drag-rate bound
  κ·max(v₀, v_t)·T_bound exceeds the existing limits (1e4 explicit, 1e7 Radau). The message
  says "at most", because the bound is loose (up to about 100× in the planning check), so
  the guard can refuse some runs that would have been fast. That over-refusal is a risk to
  measure in slice 2.
- **D5. Validation references** (formulas in the next section). **R1-R3** the exact
  vertical solution (rise with `tan`, fall with `tanh`, and the full up-and-down flight);
  **R4** terminal speed √(mg/c); **R5** the energy balance KE + PE + W = E₀ with
  dW/dt = c|v|³; the **c → 0 limit** against the textbook vacuum formulas (written in the
  tests, not imported from the linear model's code); plus two additions the tree needed:
  **R6** the hodograph invariant, the only reference here that tests genuinely 2-D motion
  (see the seams for why), and **R7** two proved bounds (speed ≤ max(v₀, v_t); flight-time
  bound). **Comparison with linear drag: none, beyond the shared vacuum limit.** No value of
  b makes b·v equal c·v² except at one speed, so a "low-speed agreement" test would need an
  arbitrary matching speed and a tolerance with no derivation. Saying "both reduce the range"
  is a qualitative observation, not a reference.
- **D6. Input limits.** Same floors as the linear model (mass ≥ 1e-6 kg, speed ≥ 1e-3 m/s),
  c from 0 to 1e6 kg/m, and a combined limit with the same meaning as `k = b/m ≤ 1e4 s⁻¹`
  (`schemas.py:21, 48-56`): the largest drag rate in the flight, κ·max(v₀, v_t) (by R7 the
  speed never exceeds this), must be ≤ 1e4 s⁻¹ (drag acts over at least 0.1 ms). The
  "angle 0 from height 0 does not fly" rule is repeated on the new schema. A corners test
  like `tests/api/test_physics_limits.py:74-118` runs every corner: a result or a 422 with a
  reason, never a 500.
- **D7. Response, stored summary and charts.** Response: `model`, `parameters`, `solver`,
  `units`, `assumptions`, `numerical` (the existing `NumericalResult`: flight time, range,
  maximum height, apex time, impact speed, method, tolerances, counts), `terminal_speed`
  (exact closed form; `null` in vacuum, because JSON has no infinity), `vacuum` (the same
  launch with no drag, exact, labelled as such), `vertical_reference` (`null` unless the
  angle is 90°: the exact R3 values and the numerical errors against them), `diagnostics`
  (`max_energy_balance_residual`; `max_invariant_residual`, `null` for a vertical launch),
  `checks` (the shared `ValidationCheck` list, decision 12), `series` (t, x, y, speed, KE,
  PE, drag work, plus the vacuum trajectory on its own time grid). **Stored summary:**
  `numerical.*`, `terminal_speed`, `vacuum.*`, `diagnostics.*`; the vertical comparison is
  shown, not stored, so the summary has the same shape for every run. **Charts:** the
  trajectory with the vacuum trajectory dashed; speed against time with a v_t line; the
  energy budget with the conserved sum, as on the linear page. Results label every number:
  "numerical (adaptive solver, rtol …)" or "exact".
- **D8. Replay tolerances and golden run.** Tolerances follow the linear model's reasoning
  (`api/routes/physics.py:55-106`): `numerical.*` values `10·(rtol·|x| + atol)`; counts and
  solver settings exact; `terminal_speed` and `vacuum.*` 1e-12 relative (closed forms);
  `max_energy_balance_residual` absolute `10·(rtol + atol/S)`. The invariant residual's rule
  is **not yet derived** (it depends on the normalisation chosen in slice 2); slice 3 must
  give it a reason, and the CI golden check then tests it on a second CPU type. A new case is
  **appended** to `tests/api/test_registry.py:20-63` (tests index cases 4 and 5 by position,
  `tests/api/test_replay.py:103, 187`), and only its golden entry is added: the pin script
  rewrites the whole file (`tests/api/pin_golden_runs.py:113-137`), so the diff must show the
  six existing entries unchanged.
- **D9. UI.** (a) a drag-law selector on `/physics/projectile`; (b) a new page
  `/physics/projectile/quadratic-drag`, linked both ways from the linear page's header.
  **(b)**: the forms differ (b in kg/s against c in kg/m), the linear page's angle sweep is
  linear-only until 2.2, and the reference overlay only works within one model (decision
  17), so a selector would add switching logic without enabling any cross-law comparison
  yet. 2.2 (sweeps for both laws) revisits a selector. A new `QuadraticDragLab` inside
  `Workspace`, fields through `spec("QuadraticDragParameters", …)`, a `ChecksTable` under
  Validation, the reference-run panel with this model only.
- **D10. 1.6 wiring** (the "adding a model" checklist, `ARCHITECTURE.md:377-391`): the
  response union (`api/outputs.py:39-46`) and `lib/api/models.ts`; `exportTables` with
  trajectory, speed and energy tables (`lib/export/tables.ts:175`); `inputFields` and
  `summaryFields` (`lib/reference/compare.ts:62, 91`); `referenceSeries`
  (`lib/reference/overlay.ts:47`); the page map (`lib/runs/pages.ts`); a case in
  `e2e/stored-fields.spec.ts:30`; the home page's model list (`app/page.tsx`, which links
  the linear page; its layout was not checked in detail).
- **D11. Learning guide.** A new **Part 18** in `docs/LEARNING_GUIDE.md`, "Quadratic drag:
  checking a model with no exact answer": why drag grows like v² for a ball (intuition only,
  no Reynolds-number theory); terminal speed from a force balance [IB core]; the vertical
  solutions by separating variables, with `arctan` going up and partial fractions to
  `artanh` coming down [IB HL]; why the 2-D problem has no closed form (|v| couples x and y);
  validation without an exact answer (limits, invariants, energy, special cases); the
  hodograph invariant and the flight-time bound [Beyond IB]; a code walkthrough with
  `<!-- src: -->` tags; checkpoints and exercises without solutions. Also the Contents,
  Part 0, the symbol table, the name-clash box (c, b and C_d) and "Changes".
- **D12. Seams for `tdd`.** See the seams section; all five taken as proposed.

## Reference formulas (derived for this plan)
Symbols and units: m (kg), c (kg/m), g (m/s²), κ = c/m (1/m), **v_t = √(mg/c) = √(g/κ)**
(m/s), τ = v_t/g (s), drag rate κ|v| (1/s). y is up; launch from x = 0, height h.
**Status:** derived on paper here; every formula below was also checked numerically during
planning against an independent SciPy DOP853 integration (rtol = atol = 1e-12, a scratch
script, **not** a repository test): vertical flight time, apex time, apex height and impact
speed agreed to 5e-11 relative or better on four cases; the rise curve y(t) to 8e-11 m;
the invariant drifted 2e-13 to 3e-10 relative on three 2-D cases, while a deliberately wrong
force (−κ|vx|vx, −κ|vy|vy) drifted it by 0.49 and broke the energy balance by 0.22; the
flight-time bound held on five cases; the c → 0 run matched the vacuum range to 3e-11.

**R1. Rise (vertical, v > 0).** dv/dt = −g(1 + v²/v_t²). Separate:
∫dv/(1 + v²/v_t²) = v_t·arctan(v/v_t), so v_t·arctan(v/v_t) = v_t·φ₀ − g t with
φ₀ = arctan(v₀/v_t). Hence `v(t) = v_t tan(φ₀ − t/τ)`, apex time `t_a = τ φ₀` (s), and,
integrating, `y(t) = h + (v_t²/g) ln(cos s + (v₀/v_t) sin s)` with s = t/τ (computed as
`log1p(−2 sin²(s/2) + (v₀/v_t) sin s)`: the direct log of a ratio of two nearly equal
cosines cancels when drag is weak; the planning check's largest rise-curve difference,
8e-11 m, was in its weakest-drag case, but whether cancellation or the solver caused it was
**not** separated). Apex height above launch:
`H = (v_t²/2g) ln(1 + v₀²/v_t²)` (m), computed with `log1p`.

**R2. Fall from rest (vertical, from height Y, time s after the apex).** With w = −v > 0:
dw/dt = g(1 − w²/v_t²); partial fractions give `w(s) = v_t tanh(s/τ)` and the drop
`d(s) = (v_t²/g) ln cosh(s/τ)` (m). Landing when d = Y: with X = gY/v_t²,
`s_L = τ arcosh(eˣ)`, computed as `τ asinh(√expm1(2X))` (no cancellation when X is small);
impact speed `v_t √(1 − e^{−2X})`, computed as `v_t √(−expm1(−2X))`.

**R3. Vertical launch (θ = 90°).** Y = h + H, flight time `T = t_a + s_L`. From the ground
(h = 0), e^{2X} = 1 + v₀²/v_t², so the impact speed is `v₀ v_t / √(v₀² + v_t²)` (< v₀:
energy is lost). Up and down differ: going up, gravity and drag both slow the ball (`tan`);
coming down they oppose (`tanh`). Hence a checkable property: from the ground the fall takes
longer than the rise. Limits: as v_t → ∞ (c → 0), t_a → v₀/g, H → v₀²/2g and the impact
speed → v₀ (Taylor series of arctan and ln(1 + x)).

**R4. Terminal speed.** mg = c v_t² gives `v_t = √(mg/c)`. From R2, the fall approaches it
exponentially: v_t − w ≈ 2v_t e^{−2s/τ}, so after 20τ the gap is below 1e-17·v_t, far
under rounding; a long-fall test can then require the impact speed to equal v_t to solver
accuracy. In 2-D, vx decays (dvx/dt = −κ|v|vx) and the velocity tends to (0, −v_t).

**R5. Energy balance.** d/dt(½mv² + mgy) = F_drag·v = −c|v|³, so `KE + PE + W = E₀`
with `dW/dt = c|v|³` (J/s). **W must be coded from c|v|³ directly, not as −F·v from the
force function**; otherwise a wrong force law would also give a "consistent" W and the check
would catch nothing.

**R6. Hodograph invariant (2-D, vx₀ > 0).** Drag points along v, so only gravity turns the
velocity: with θ the velocity's angle, dθ/dt = −g cos θ / v. Dividing,
dvx/dθ = κ vx³ / (g cos³θ), so d(1/vx²)/dθ = −(2κ/g) sec³θ. Using
∫sec³θ dθ = ½(sec θ tan θ + ln(sec θ + tan θ)):

`I = 1/vx² + (κ/g)·[v·vy/vx² + asinh(vy/vx)]` is constant (s²/m²).

(ln(sec θ + tan θ) = asinh(tan θ) = asinh(vy/vx), which avoids the cancellation in
ln((v + vy)/vx) when vy ≈ −v late in a fall.) vx never changes sign, since dvx/dt is
proportional to −vx, so I is defined for the whole flight when vx₀ > 0. The literature
calls this approach the hodograph method; **no literature source was checked for this plan**,
so the derivation above, plus the numerical check, is the reference. The residual's
normalisation (for example max|I − I₀| / max(1/vx²)) is decided in slice 2, because
1/vx² grows large as vx decays in long flights.

**R7. Two proved bounds** (used for the cap and the guard; tests check they hold).
(i) **Speed ≤ max(v₀, v_t)** throughout: d(½v²)/dt = −g vy − κv³ ≤ v(g − κv²), which is
negative whenever v > v_t. (ii) **Flight time ≤ T_bound = vy₀/g + T_fall**: going up,
dvy/dt ≤ −g, so the rise lasts at most vy₀/g and climbs at most vy₀²/2g; coming down,
d|vy|/dt = g − κv|vy| ≥ g − κV|vy| with V = max(v₀, v_t), so the ball falls at least as fast
as under *linear* drag with k = κV. T_fall is the exact linear-drag time to fall from rest
from h + vy₀²/2g with that k (the existing `analytical.flight_time`, `analytical.py:178`,
used only as a cap, as the linear model already does). Loose: up to about 100× in the
planning check (39.8 s against a bound of 3989 s at v₀ = 1000 m/s).

## Seams (where tests attach; each with what it catches and misses)
1. **Reference functions** (`quadratic_reference.py`, pure). Tests: the formulas satisfy
   their ODEs (central differences, as for the linear closed form); c → 0 Taylor limits;
   the v₀v_t/√(v₀² + v_t²) identity; the fall-longer-than-rise property; cancellation-prone
   forms against a 50-digit `decimal` evaluation (stdlib). *Catches* derivation and
   cancellation errors. *Misses* everything about the solver and all genuinely 2-D motion.
2. **Numerical integrator** (`quadratic_numerical.integrate`, pure). Tests: vertical runs
   against R1-R3 (3 solvers); c → 0 against textbook vacuum formulas; long fall reaches
   v_t; energy balance; the invariant; both R7 bounds on every step node; shallow launches
   do not "land" at t = 0; error falls as rtol tightens; a wrong-coupling mutant is caught.
   *Catches* RHS errors, including the 2-D coupling bug that the vertical tests cannot see
   (with vx = 0, −κ|v|v and −κ|vy|vy agree) and that the c → 0 and terminal-speed tests
   also miss; *only R5 (with W coded independently) and R6 catch it*. Event bugs. *Misses*
   API, bounds and replay.
3. **Model orchestration** (`quadratic_model.run`, pure). Tests: the stiffness guard refuses
   with a reason; `vertical_reference` only at 90°; `terminal_speed` null at c = 0; checks
   present and labelled. *Catches* assembly and labelling bugs. *Misses* the HTTP contract.
4. **API and registry.** Tests: validation (NaN, ±Infinity, bounds, the κ·max(v₀, v_t)
   rule); the corners test; registry rebuild gives the same hash; one tolerance rule per
   stored field; golden run; replay and recompute cases (picked up from `CASES`); the
   existing golden digests unchanged. *Catches* contract, reproducibility and regression
   bugs. *Misses* the browser.
5. **Frontend.** Vitest for the lab (fields from `openapi.json`, run, stale note, charts,
   checks), `exportTables`, `compare`, `overlay`; Playwright for the page and the
   stored-fields case. *Catches* UI and field-drift bugs. *Misses* scientific errors, which
   seams 1-2 own.

## Slices (test-first, one commit each)
1. **Reference formulas** (seam 1): R1-R4, R6, R7 in `quadratic_reference.py`, with their
   tests written first.
2. **Integrator and model run** (seams 2-3): `quadratic_numerical.py`, `quadratic_model.py`;
   decide and justify the invariant residual's normalisation; measure the guard's
   over-refusal on a grid and the observed accuracy for `SCIENTIFIC_VALIDATION.md`.
3. **API** (seam 4): `quadratic_schemas.py`, the route and `ModelEntry` (inputs, summary,
   tolerances with reasons, headline, rebuild), registry, response union, corners test,
   appended golden run, `make api-types`.
4. **Frontend** (seam 5): page, lab, results, fields, links; the D10 wiring; Vitest; the
   Playwright page test and stored-fields case.
5. **Docs**: a `SCIENTIFIC_VALIDATION.md` section (proved, tested and observed kept
   separate) and updating the linear model's "linear drag only" limitations
   (`SCIENTIFIC_VALIDATION.md:140-142, 380`); `ARCHITECTURE.md` layout and endpoint table;
   `README.md`; `ROADMAP.md` (the capability map's "quadratic drag" and 2.1's status); the
   learning guide's Part 18 (D11). Then `scripts/check.sh --e2e` and a fresh-context review.

## Risks
- **Smoothness at a vertical apex.** |v|v is once but not twice differentiable at v = 0,
  which only a vertical launch reaches (with vx₀ > 0, v never vanishes). High-order methods
  may lose accuracy across that instant; the planning check still matched R3 to 5e-11, but
  the tolerances in the vertical tests must be justified with that in mind.
- **Loose flight-time bound** (D4): the guard may refuse feasible runs; measure, then decide
  in slice 2 whether the message or the bound needs tightening.
- **The invariant's conditioning**: 1/vx² grows like e^{2gt/v_t} late in a long flight, so
  the residual needs a scale-aware normalisation and, perhaps, `null` when vx has decayed
  far; its replay tolerance is not derived yet (D8).
- **Duplicated event logic** with `numerical.py` until 2.4 (D3).
- **Golden re-pin side effects** (D8): on a different CPU the pin script would also rewrite
  the six existing entries; keep them unchanged.
- **Names**: c (kg/m), b (kg/s) and C_d (dimensionless) are easy to confuse; the guide's
  name-clash box and the field descriptions must say which is which.
- **Unverified:** the hodograph-method literature (not checked); the home page and
  navigation layout (not read in detail); whether the e2e suite's run time grows noticeably.

## Out of scope
The angle sweep for quadratic drag (2.2); the oscillators (2.3); a fixed-step integrator
study or symplectic methods for quadratic drag (2.4); generic sweeps (2.5); animation (2.6);
any change to the linear model, its sweep or its integrator study; overlaying linear and
quadratic runs; wind, spin and lift, buoyancy, and C_d varying with speed. The capability
map's "best angle against drag strength" and "drag-law comparison" are **not** in the
Phase 2 paragraph, so this plan does not schedule them; where they belong is the author's
roadmap decision.

## Genuine stops found
None. Checked: no new dependency (NumPy, SciPy and the stdlib `decimal` suffice); no
database migration (a new model, endpoint, registry entry and union member are purely
additive, and existing responses and digests are unchanged, which the golden test enforces);
no new security surface (bounded numeric inputs through `StrictModel`, nothing new stored);
no roadmap scope or order change; every reported number has an independent reference (R1-R7,
the vacuum formulas) or is labelled a numerical approximation.
