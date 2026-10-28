# Roadmap 2.2 plan: angle sweeps for both drag laws (decided by default)

Written by the autopilot on 2026-10-28 (planning subagent). **Decided by the autopilot by
default on 2026-10-28**: the author delegated Phase 2's design questions ("agree to
defaults"), so the autopilot ran `grilling` on itself and accepted its own recommendation for
every question below (D1-D15). Every decision is **reversible**, and the author reviews it;
nothing is built until this plan has been read. PR #13 (roadmap 2.1) is merged (`origin/main`
is at `646e996`), so building can start on a new branch and PR.

**Scope: exactly the 2.2 row**, "Angle sweeps for both drag laws". The linear-drag sweep
already exists (`physics.projectile.angle_sweep` v1.0.0); 2.2 adds the quadratic-drag sweep
and leaves the linear one exactly as it is. The capability map's "best angle against drag
strength" and "drag-law comparison" are **not** in scope; they are listed under "Out of scope
(awaiting the author)" with what adding them would cost.

**The fact that drives most choices** (the same one as in 2.1): the linear sweep hashes and
stores `ProjectileParameters` minus the launch angle, plus `n_angles`
(`api/routes/physics.py:300-303`), and its response, digest and golden run are pinned
(`tests/api/golden_runs.json`, entry 3). A `drag_law` field on `AngleSweepRequest`
(`physics/projectile/schemas.py:170-181`) would enter every rebuilt request, so every stored
linear sweep would hash differently and replay would refuse it with 409; and a quadratic
sweep needs inputs the linear one does not have (`drag_constant` in kg/m, and the solver
settings, because there is no exact range). So the quadratic sweep is a **new model**, as
quadratic drag itself was (ARCHITECTURE decision 18).

**The second fact:** the linear sweep is cheap because every range is a closed form
(`angle_sweep.py:78-89`). A quadratic sweep is about 100 numerical solves (one per angle,
plus 6-20 for the refinement). Measured (scratch, one machine, see "References"): 0.4 s for
the default 91 angles with DOP853, but about 10 s with Radau at `c = 0.1 kg/m`, and single
Radau runs at tight tolerances in hard corners take 3-4 s each. So 2.2 needs a **work limit**,
which the linear sweep never did.

## What 2.2 builds
The quadratic-drag page gets the same panel the linear page has: **"Range against launch
angle"**. Keep the speed, height, mass, drag and gravity fixed, try every launch angle from
0° to 90°, draw range against angle, and find the angle that throws furthest. With no drag
that angle is 45° from the ground, a result you can prove with `sin 2θ`. With quadratic drag
there is no formula for the range at all, so each point on the curve is one full computer
simulation (the 2.1 model), and the best angle has to be **searched for**, not calculated.
That raises two honest questions the panel answers: *how accurately do we know the best
angle* (the top of the curve is flat, so a tiny error in the range moves the best angle a
lot more than you would guess), and *how do we know it is right* without a formula to compare
with. The answers: with no drag the sweep must give 45° and `v₀²/g` again; every point must
equal a single 2.1 run at that angle; for weak drag a hand-derived approximation predicts how
far below 45° the best angle moves (about 6.02° × (v₀/v_t)²); and every one of the ~100 runs
passes the 2.1 checks (energy balance, the conserved quantity, the proved bounds). The chart
shows the drag curve with the drag-free curve dashed for comparison. Sweeps save, replay,
recompute, export and compare like every other model.

## Design tree and rounds (self-grilled)
- **Round 1** (no prerequisites): D1 new model or an option; D2 what "both drag laws" means
  on screen; D3 which references validate it.
- **Round 2** (after D1-D3): D4 how one angle is computed (reuse of the 2.1 run); D5 how the
  best angle is located; D6 its stated accuracy; D7 input rules and the stiffness guard per
  angle; D8 limits on angles and total work; D9 where the code lives.
- **Round 3** (after D4-D9): D10 response, stored summary and per-run checks; D11 replay
  tolerances and golden run; D12 UI; D13 the 1.6 export/compare/overlay wiring; D14 docs and
  learning guide; D15 seams for `tdd`.

Each decision below lists the options, the **default taken** (in bold) and why.

## Decisions
- **D1. A new sweep model, or a drag-law option?** (a) a `drag_law` field on the existing
  sweep; (b) a `sweep` mode on the 2.1 quadratic model's request; (c) a new model.
  **(c)**: `physics.projectile.quadratic_angle_sweep` v1.0.0, "Range versus launch angle
  (quadratic drag)", endpoint `POST /api/v1/physics/projectile/quadratic-drag/angle-sweep`.
  (a) breaks replay of every stored linear sweep and forces a version bump and re-pin for
  unchanged physics (driving fact). (b) changes the 2.1 model's request and response shape,
  so its digests and golden run change too. The id avoids the prefix
  `physics.projectile.quadratic_drag.` so no code that matches ids by prefix can confuse the
  two models (none was found: the lab comes from the first segment only,
  `api/routes/experiments.py:53`). The linear model, its sweep and the 2.1 model keep their
  versions and digests; the golden test enforces it.
- **D2. What "both drag laws" means on screen.** (a) each law's sweep on its own page, under
  that page's simulation, as the linear page does now (`ProjectileResults.tsx:131-136`);
  (b) one page that runs both sweeps and draws both curves on one chart; (c) a drag-law
  selector (2.1 D9 said 2.2 would revisit it). **(a)**. The quadratic chart shows the
  drag-free curve dashed (exact, D10), so both pages share the same reference curve. (b) is
  the capability map's separate "drag-law comparison": it needs a rule for which `b` matches
  which `c` (no `b` makes `b·v` equal `c·v²` except at one speed, 2.1 D5), and either a
  cross-model overlay, which decision 17 deliberately excludes
  (`ARCHITECTURE.md:344-347`), or a combined model. That is the author's call (Out of
  scope). (c) still adds switching logic between two forms with different units (b in kg/s,
  c in kg/m) without enabling any comparison, so the 2.1 answer stands: no selector.
- **D3. Validation references** (formulas in the next section). **RS1** the vacuum limit:
  at `c = 0` every range equals the textbook vacuum range, and the best angle and range equal
  the closed form `tan θ* = v₀/√(v₀² + 2gh)`, `R* = (v₀/g)√(v₀² + 2gh)` (45° and `v₀²/g`
  from the ground). **RS2** consistency: every sweep point is bit-identical to a single 2.1
  run at that angle. **RS3** a weak-drag perturbation result derived for this plan (from the
  ground): `θ* = 45° − 6.0183°·ε + O(ε²)` and `R*/(v₀²/g) = 1 − 0.783976·ε + O(ε²)` with
  `ε = (v₀/v_t)²`. It makes "the best angle falls below 45° with drag" **proved to first
  order in ε** (weak drag only); for stronger drag, and for "it keeps falling as drag grows",
  the evidence is **observed** on a grid and labelled so. **RS4** an independent
  high-accuracy integration (its own right-hand side, DOP853 at rtol = 1e-13, inside the
  test) for the best angle at stronger drag, plus an independent dense scan around the
  reported optimum (as the linear sweep's test does, `tests/physics/test_angle_sweep.py:96-106`).
  **RS5** exact special points: 90° gives range exactly 0 and is also checked against the
  exact vertical flight by the 2.1 run itself; 0° from the ground is "no flight", range exactly
  0. **RS6** the 2.1 per-run checks at every angle. **Comparison with the linear sweep: none
  beyond the shared vacuum limit**, for 2.1 D5's reason; each sweep's `c → 0` / `b → 0` limit
  is tested against the textbook formulas, not against the other model.
- **D4. How one angle is computed.** (a) call `quadratic_model.run` per angle; (b) call the
  lower-level `integrate` with a copied cap; (c) refactor `run` into a shared solve step.
  **(a)**, with `n_samples = 10` (the schema minimum; the series is discarded). It makes RS2
  true by construction (the same guard, the same cap `2·T_bound`, the same events, the same
  checks: `quadratic_model.py:508-540`), and changes no 2.1 code. The cost of resampling 10
  points twice is negligible next to the solve. The setup is built exactly as the 2.1 route
  builds it (`math.radians(angle_deg)`, `api/routes/physics.py:332-340`), so 90° is exactly
  vertical (`quadratic_numerical.py:47-58`) and its range is exactly 0. 0° from the ground is
  **not** run (2.1 refuses it, `quadratic_schemas.py:101-106`): its point is range, flight
  time and height exactly 0, labelled "no flight", as the linear sweep's closed form gives.
- **D5. Locating the best angle.** (a) the best grid point only; (b) the best grid point
  refined by SciPy's bounded Brent search on the neighbouring grid interval, as the linear
  sweep does (`angle_sweep.py:105-117`); (c) golden-section search; (d) a parabola through
  the best three grid points; (e) solving dR/dθ = 0 with sensitivity equations. **(b)**,
  `xatol = 1e-7°` and the same fallback (if a grid point beats the refined value, keep the
  grid point; this also handles a maximum at 0° or 90°). Brent is golden section plus
  parabolic steps, so (c) is its slower special case; (d) gives no stated accuracy; (e) is a
  new solver for no gain. The grid point is **never** reported as the optimum without the
  refinement; a best angle at the edge of the range is labelled as such. Brent finds a
  *local* maximum, so the response also reports how many interior peaks the grid shows (D10);
  one peak was observed in every case measured (RS5 table), which is evidence, not a proof.
- **D6. The best angle's stated accuracy.** (a) Brent's stopping tolerance only (~1e-6°);
  (b) a per-run estimate from the flatness of the peak; (c) only the observed accuracy in
  `SCIENTIFIC_VALIDATION.md`. **(b) plus (c)**. (a) would overstate it: Brent stops within
  ~1e-6° *of the peak of the computed curve*, but the computed curve differs from the true
  one by the solver's error. Per run the response gives `best_angle_uncertainty_deg`,
  `u = 2√(ε_R/K)` (RS4 below; ε_R = 10·(rtol·R̂ + atol), K = |R''| from the grid's second
  difference), labelled **"estimate, not a bound"**, and `null` with the reason when the best
  angle is at an edge or the grid curvature is not negative. It is pessimistic: about 2e-3°
  at default tolerances, while the measured error against an independent reference was
  ≤ 3e-6° (RS4 status), because the solver's error is smooth in the angle rather than random.
  That gap is stated, not hidden; the UI shows the angle to 2 decimals, which the estimate
  supports.
- **D7. Input rules and the stiffness guard per angle.** (a) validate every angle as a
  separate 2.1 request; (b) validate once, at the smallest angle that is actually run;
  (c) skip angles that fail and leave holes (`null`). **(b)**: the sweep request is valid iff
  a 2.1 request (`QuadraticDragRequest`, `quadratic_schemas.py:116-144`) at that angle with
  the same parameters and solver is valid. The drag-rate and atol rules do not depend on the
  angle, and the drag-free flight time `(vy₀ + √(vy₀² + 2gh))/g` grows with the angle, so the
  1 µs rule holds at every larger angle if it holds at the smallest (0° when h > 0, else the
  first grid step 90°/(n − 1)). The 422 message is prefixed "at the sweep's smallest angle
  …°:". The launch angle in the parameters is ignored, as in the linear sweep, so 0° from the
  ground is allowed there (`tests/api/test_physics_limits.py:121-125`). (c) puts holes in the
  curve and a best angle that may sit next to one. **Stiffness guard:** before any solve, the
  drag-time bound (`quadratic_model.drag_time_bound`, `quadratic_model.py:209-233`) is
  computed at every grid angle, and an explicit method is refused (422) if any exceeds 1e4,
  naming the worst angle; refinement angles are guarded again inside `run`
  (`quadratic_model.py:512`), so a refusal there is still a 422 with its reason.
- **D8. Limits on angles and total work.** (a) the linear sweep's `n_angles` 10 to 361,
  default 91 (`schemas.py:175-180`), and no other limit; (b) a lower `n_angles` maximum;
  (c) a wall-clock timeout; (d) a budget on the **total right-hand-side evaluations** of the
  sweep, checked after each run. **(a) plus (d)**: `MAX_SWEEP_RHS_EVALUATIONS`, provisionally
  3e5 (8-43 µs per evaluation measured, so roughly 3-13 s, plus at most one run in progress),
  its final value set by measurement in slice 2. Over budget: 422, "the sweep needed more than
  N evaluations after k of n angles; use fewer angles, a looser tolerance or DOP853 where the
  drag-time bound allows". (c) is not reproducible (it depends on the machine's load), so a
  replay could fail where the original succeeded. (b) alone does not bound cost, because one
  Radau run can take 4 s. Counting evaluations is deterministic on one machine; on another
  CPU a sweep very near the budget could be refused (Risks). Same defaults as the linear
  sweep keep the two panels alike.
- **D9. Where the code lives.** (a) generalise `angle_sweep.sweep` to take any range
  function; (b) extract a generic "sweep and refine" helper into `numerics/`; (c) a new module
  that repeats the ~25 lines of grid-and-Brent logic. **(c)**:
  `physics/projectile/quadratic_angle_sweep.py` (the sweep, `MODEL_INFO`, `UNITS`, the note
  and `run_angle_sweep`), the request and response appended at the **end** of
  `quadratic_schemas.py`, the route and `ModelEntry` appended at the end of
  `api/routes/physics.py`. (a) edits the linear sweep's code path and the learning guide's
  excerpt of it (`docs/LEARNING_GUIDE.md:2500`, `angle_sweep.py:99-117`). (b) is premature:
  roadmap 2.5 ("Generic sweeps") is where a shared sweep layer belongs, with more than two
  users; the duplication is recorded as a risk, as 2.1 did for the event logic.
- **D10. Response, stored summary and per-run checks.** Request: `parameters`
  (`QuadraticDragParameters`, launch angle ignored), `solver` (`SolverSettings`), `n_angles`,
  `save_experiment`. Response: `model`, `parameters`, `solver`, `units`, `assumptions`,
  `angles_deg`, `ranges`, `flight_times`, `max_heights` (numerical; the linear sweep's names),
  `vacuum_ranges` (exact, the same angles), `best_angle_deg`, `best_range` (numerical),
  `best_angle_uncertainty_deg` (estimate or `null`) with `best_angle_note`,
  `vacuum_best_angle_deg`, `vacuum_best_range` (exact), `terminal_speed` (exact, `null` in
  vacuum), `n_runs` and `n_rhs_evaluations` (the whole sweep), `checks`, `method_note`,
  `metadata`. **Checks** (the shared `ValidationCheck` list): one per 2.1 check id, aggregated
  over every run: `passed` only if every run passed; `value` and `threshold` from the run with
  the largest value/threshold (thresholds differ per angle, e.g. the invariant's uses
  min(vx₀, v_t)), and the note names that angle and the number of runs; plus two
  informational checks, "interior peaks on the grid" (expected 1; more means the refinement
  may have found a local maximum, shown as not passed) and "runs and evaluations" (against the
  budget). A scratch run of the 2.1 checks at all 361 angles of four cases × three methods at
  default settings had **no failure** (scratch, one machine). **Stored summary:**
  `best_angle_deg`, `best_range`, `best_angle_uncertainty_deg`, `vacuum_best_angle_deg`,
  `vacuum_best_range`, `terminal_speed`, `n_rhs_evaluations`; the curves and checks are shown,
  not stored (decision 5). Hashed inputs: `parameters` without `launch_angle_deg`, `solver`,
  `n_angles`; `digest_exclude` the echoed launch angle, as the linear entry does
  (`api/routes/physics.py:300-317`).
- **D11. Replay tolerances and golden run.** With `rtol' = max(rtol, 1e-10)` (2.1 A7's
  floor, `api/routes/physics.py:448`): `best_range` `10·(rtol'·|x| + atol)` (the solver rule);
  `best_angle_deg` absolute `max(1e-5°, u)`, the run's own stated uncertainty, floored by the
  linear sweep's rule (`api/routes/physics.py:278-283`); `vacuum_best_*` and `terminal_speed`
  1e-12 relative (closed forms); `n_rhs_evaluations` exact (a count, as in 2.1).
  `best_angle_uncertainty_deg` is **not yet derived**: it comes from a second difference of
  three computed ranges, which a flip of the best grid point on another CPU would change
  sharply; slice 3 measures it by the last-bit emulation 2.1 used (scratch result so far: last
  bits moved the best angle by at most 1e-5° and the best range by at most 1.5e-13 relative,
  RS4 status). A case is **appended** to `tests/api/test_registry.py:20-70` (tests index cases
  1, 4 and 5 by position, `tests/api/test_replay.py:103, 179, 187`), and only its golden entry
  is added; the diff must show the seven existing entries unchanged.
- **D12. UI.** (a) a separate `QuadraticAngleSweepPanel` copied from `AngleSweepPanel`;
  (b) make `AngleSweepPanel` serve both sweep models through a small per-model adapter (run
  function, model id, labels, optional vacuum curve and uncertainty). **(b)**: the panel hard-
  codes the linear model id, `runAngleSweep` and `drag_coefficient`
  (`AngleSweepPanel.tsx:40, 52, 70`); frontend code has no digests, and its Vitest tests guard
  the linear behaviour. If the adapter turns out awkward in slice 4, fall back to (a) and say
  so in the commit. On the quadratic page the panel sits under the results, keyed by run, and
  sends that run's `parameters` and `solver`. Chart: the drag curve, the vacuum curve dashed
  and labelled "no drag (exact)", markers at both best angles; the stats show "Best angle
  (numerical) 42.98° ± 0.002° (estimate)", the maximum range and the vacuum values
  "(formula)". The quadratic page's `PAGE_MODELS` (`QuadraticDragLab.tsx:36`) gains the sweep
  id for reopening and the reference run, with the linear page's note "Run the simulation,
  then sweep the launch angle." (`ProjectileLab.tsx:74-75`).
- **D13. 1.6 wiring** (the checklist, `ARCHITECTURE.md:416-430`): the response union
  (`api/outputs.py:45-52`) and `lib/api/models.ts:14-16`; `exportTables`: `range_vs_angle`
  with angle, range, flight time, maximum height and vacuum range columns (as
  `lib/export/tables.ts:85-99`, dispatch at 213-216); `inputFields` and `summaryFields`
  (`lib/reference/compare.ts:71-77, 118-125` as the model); `referenceSeries`: the computed
  range curve under chart id `range` (`lib/reference/overlay.ts:93-104`); the page map
  (`lib/runs/pages.ts:5-7`) to `/physics/projectile/quadratic-drag`; two cases in
  `e2e/stored-fields.spec.ts` (one with drag and a non-default solver and odd `n_angles`, one
  in vacuum so the `null`s are covered, as 2.1 did at lines 37-48); `api/registry.py:20-27`.
- **D14. Docs and learning guide.** A new **Part 19** in `docs/LEARNING_GUIDE.md`, "Angle
  sweeps for both drag laws: finding a maximum you cannot write down": why one sweep is ~100
  simulations and why that needs a work budget counted in evaluations, not seconds
  (reproducibility); grid plus Brent [IB HL ideas: maximum where the gradient is zero];
  flatness at the top: `R(θ* + δ) ≈ R* − ½Kδ²`, so an error ε in the range moves the angle
  by about √(ε/K), with a worked number [IB HL]; why drag lowers the best angle (intuition:
  high, long flights lose more to drag) and the weak-drag result `θ* ≈ 45° − 6.02°(v₀/v_t)²`
  with ε = (v₀/v_t)² as the dimensionless drag strength [Beyond IB, derivation in outline];
  proved to first order against observed beyond it; a code walkthrough with `<!-- src: -->`
  tags; checkpoints and exercises without solutions. Part 11 gets a pointer to Part 19; also
  the Contents, Part 0, the symbol table (ε, K, u) and "Changes". **Tags to update:** the
  new imports at the top of `api/routes/physics.py`, `api/outputs.py`, `lib/api/client.ts`
  and `lib/reference/compare.ts` shift the lines of the guide's tags at
  `LEARNING_GUIDE.md:2002, 2055, 2585, 3007, 3145`; no script checks tags (none found), so
  slice 5 re-checks every tag in the touched files by hand. Also `SCIENTIFIC_VALIDATION.md`
  (a new section; the linear sweep's "Linear drag only" limitation, line 381, updated),
  `ARCHITECTURE.md` (decision 19, layout, endpoint table), `README.md`, `ROADMAP.md` (2.2 ✅
  and the capability map's "angle sweep for both drag laws").
- **D15. Seams for `tdd`.** See the seams section; all five taken as proposed.

## Reference formulas (derived for this plan)
Symbols and units: as 2.1 (m kg, c kg/m, g m/s², κ = c/m 1/m, v_t = √(mg/c) m/s), plus
θ the launch angle (rad in formulas, degrees in the API), R(θ) the range (m), K = |R''(θ*)|
(m/rad²), and **ε = κv₀²/g = (v₀/v_t)²**, the dimensionless drag strength (ε = 0 in vacuum).
**Status:** derived on paper here; checked numerically in scratch scripts (one machine,
SciPy 1.18.1, NumPy 2.5.4; **not** repository tests), as stated under each item.

**RS1. Vacuum.** `R_vac(θ) = v₀cos θ · (v₀ sin θ + √(v₀² sin²θ + 2gh))/g` (m). Maximum at
`tan θ* = v₀/√(v₀² + 2gh)`, `R* = (v₀/g)√(v₀² + 2gh)` (`angle_sweep.py:21-26`), so 45° and
`v₀²/g` when h = 0. At c = 0 the 2.1 solver integrates the quadratic path exactly apart from
rounding; scratch: the sweep's best angle was within 7e-7° of 45° (Brent's stopping limit,
√ε_mach·45° ≈ 6.6e-7°) and its best range within 9e-16 relative, all three methods.

**RS2. Consistency.** Sweep point at θ ≡ `quadratic_model.run` at θ (bit-identical
`numerical.range`, `flight_time`, `max_height`), by D4.

**RS3. Weak drag, from the ground (first-order regular perturbation).** Zeroth order: u =
v₀cos θ, w = v₀sin θ, vy = w − gt, T₀ = 2w/g, speed q = √(u² + vy²). First-order velocity
corrections: δvx' = −κqu, δvy' = −κq·vy. The landing shifts by δT = δy(T₀)/w, so
δR = δx(T₀) + u·δT. Using the symmetry of the vacuum path about its apex (τ = t − T₀/2,
vy = −gτ), the odd parts vanish and

`δR = −(κu/g²)·[w·J₀ + J₂/w]`, with `J₀ = ∫_{−w}^{w} √(u² + s²) ds = w v₀ + u² asinh(w/u)`
and `J₂ = ∫_{−w}^{w} s²√(u² + s²) ds = [w(2w² + u²)v₀ − u⁴ asinh(w/u)]/4`.

In dimensionless form, `R(θ) = (v₀²/g)·[sin 2θ − ε F(θ)] + O(ε²)` with (c = cos θ,
s = sin θ, A = asinh(tan θ))

`F(θ) = c s² + c³ s A + c(1 + s²)/4 − c⁵A/(4s)`.

At 45°: `F(π/4) = 7/(8√2) + (3/16) ln(1 + √2) = 0.783976` and
`F'(π/4) = (3√2 − ln(1 + √2))/8 = 0.420158` (derived by hand for this plan; matches a central
difference of F, step 1e-5, to 8e-11, that difference's own error size). Setting
d/dθ[sin 2θ − εF] = 0 near π/4, where 2cos 2θ ≈ −4(θ − π/4):

`θ* = 45° − (180/π)·ε·F'(π/4)/4 + O(ε²) = 45° − 6.0183°·ε + O(ε²)`,
`R*/(v₀²/g) = 1 − 0.783976·ε + O(ε²)` (the angle shift enters R* only at second order).

F'(π/4) > 0, so **to first order in ε the best angle is below 45°**: proved for weak drag
(the O(ε²) remainder is not bounded explicitly, so "weak" is not quantified). Scratch checks:
F against numerical quadrature (`scipy.integrate.quad`) at four angles, agreement to 3e-17;
against an independent DOP853 integration at rtol = 1e-13 (v₀ = 20 m/s), the best-angle
shift divided by the first-order prediction was 0.99956, 0.99459, 0.98393, 0.94880 at
ε = 1e-3, 1e-2, 3e-2, 1e-1 (the deviation grows like ε, as the O(ε²) term predicts), and
R(45°)'s first-order residual was 7.5e-7, 7.4e-5, 6.5e-4, 6.8e-3 of v₀²/g (≈ 0.75 ε², slope
2). At ε = 1e-4 the reference's own best angle (±1e-6°) limits the comparison, so tests use
ε ≥ 5e-3. Default inputs (v₀ = 20 m/s, c = 0.01 kg/m, m = 1 kg) have ε = 0.41: too large for
the first-order formula (it gives 42.55° against 42.98° computed), which the guide says.

**RS4. Flatness and the stated accuracy.** Near the top, `R(θ) ≈ R* − ½K(θ − θ*)²`. If the
computed curve is within ε_R of the true one everywhere near the top, its maximiser θ̂ has
`R(θ̂) ≥ R* − 2ε_R`, so `|θ̂ − θ*| ≤ 2√(ε_R/K)` (rad), to the quadratic approximation; the
plan takes ε_R = 10·(rtol·R̂ + atol), the project's solver-error scale, which is **not** a
proved bound on the global error. K is estimated from the grid,
`K ≈ |R(θ_{i+1}) − 2R(θ_i) + R(θ_{i−1})|/Δ²`. Vacuum check: R = (v₀²/g) sin 2θ gives K = 4R*
at 45°, so at rtol = atol = 1e-10, `u ≈ 2√(10·1e-10/4) rad = 1.8e-3°`; the scratch
estimate, computed as √(2ε_R/K), was 1.3-2.0e-3° for c = 0.001 to 1 kg/m (so 1.9-2.8e-3° as
2√(ε_R/K)). **Observed** (scratch): against the independent integration, the default-tolerance best angle was within 2.9e-6° (12 cases: c ∈ {0, 1e-4,
0.01, 0.1}, three methods); last-bit emulation (each drag evaluation × (1 ± 1 or 2 ulp), 24
cases, rtol 1e-10 and 1e-6) moved the best angle by at most 1.0e-5° and the best range by at
most 1.5e-13 relative.

**RS5. Observed properties (not proved).** Scratch, independent integration, v₀ = 20 m/s, a
0.5° grid then Brent, ε from 1e-3 to 1e3 (10 values), h ∈ {0, 0.5, 5}·v₀²/g:

| h / (v₀²/g) | best angle at ε = 1e-3 → 1 → 1e3 | Interior peaks | Falls as ε grows |
|---|---|---|---|
| 0 | 44.994° → 40.98° → 20.34° | 1 in all 10 | yes |
| 0.5 | 35.25° → 26.24° → 6.11° | 1 in all 10 | yes |
| 5 | 16.76° → 12.55° → 6.11° | 1 in all 10 | yes, but nearly flat between ε = 1 and 3 (12.549° → 12.527°) |

At strong drag the two heights give the same answer (from 30 on), because the ball has lost
its horizontal speed before it lands. Tests check the "falls as drag grows" property only at
h = 0 and only on measured grids, labelled observed.

**Cost (scratch, one machine).** Per evaluation 8-43 µs (DOP853 cheapest, Radau dearest).
Default 91-angle sweeps at v₀ = 20 m/s: DOP853 0.2-0.4 s, RK45 0.15-0.8 s, Radau 0.3-10 s
(c = 0 to 0.1 kg/m; Radau 282 000 evaluations at c = 0.1). Single Radau runs at rtol = 1e-13
in hard corners (v₀ = 1e4 m/s, c = 1 kg/m, h up to 1e5 m): 3-4 s and ~1e5 evaluations each;
the explicit methods are refused there by the drag-time guard. Brent used 6-19 extra runs.

## Seams (where tests attach; each with what it catches and misses)
1. **Weak-drag reference** (a test-side helper next to the physics tests, pure; nothing in
   the product depends on it). Tests: F against `scipy.integrate.quad` of the J integrals and
   against a 50-digit `decimal` evaluation; F(π/4) and F'(π/4) against their closed forms.
   *Catches* derivation and algebra errors in RS3. *Misses* everything about the code.
2. **The sweep core** (`quadratic_angle_sweep.sweep`, pure). Tests: RS2 bit-identity at
   every grid angle and at a refinement angle; RS1 at c = 0 (per-angle ranges to 1e-13
   relative, best angle to 1e-5°, from h = 0 and four heights); RS3 as an **order test**
   (ε ∈ {5e-3, 1e-2, 2e-2, 4e-2}: the deviation from the first-order angle and range falls
   about 4-fold per halving of ε, a fitted slope of 2 ± 0.3), not a single tolerance; RS4 at three
   stronger drags (the best angle within u of the independent integration, and a dense scan
   finds no longer range beyond rounding); RS5 at h = 0 (labelled observed); 0° from the
   ground is exactly 0 without a solve; 90° is exactly 0; a maximum at an edge keeps the grid
   point and gives `u = null`; the guard refuses before any solve and names the angle; the
   budget refuses deterministically; a wrong-coupling force mutant (−κ|vx|vx, −κ|vy|vy,
   substituted as 2.1's mutation test does, `quadratic_numerical.py:94-95`) fails the RS3
   order test (expected, since its first-order F differs, so the deviation would shrink
   like ε, not ε²; **not yet measured**). *Catches* wiring, degree/radian, bracket and
   refinement bugs, and a wrong force law. *Misses* the API, replay and the browser.
3. **Model run and checks** (`run_angle_sweep`). Tests: aggregated checks pass and name the
   worst angle; a planted failing run marks the aggregate failed; the peak count; `null`s in
   vacuum. *Catches* assembly and labelling bugs. *Misses* the HTTP contract.
4. **API and registry.** Tests: validation (NaN, ±Infinity, bounds, the smallest-angle rule
   with its prefix, the atol and drag-rate rules, the launch angle ignored in results and
   hash, 0° from the ground accepted); a corners test (n_angles = 10, every method, never a
   500, each refusal explained, a time limit measured in slice 3); the budget 422; registry
   rebuild gives the same hash; one tolerance rule per stored field; the appended golden run;
   replay and recompute cases; the existing golden digests unchanged. *Catches* contract,
   reproducibility and regression bugs. *Misses* the browser.
5. **Frontend.** Vitest for the panel with both models (the linear tests unchanged),
   `exportTables`, `compare`, `overlay`; Playwright: the quadratic page sweeps, pins a sweep
   as the reference, and the two stored-fields cases. *Catches* UI and field-drift bugs.
   *Misses* scientific errors, which seams 1-3 own.

## Slices (test-first, one commit each)
1. **Weak-drag reference** (seam 1): the RS3 helper and its tests, written first; the RS1
   vacuum functions of the new module with their tests.
2. **Sweep core and run** (seams 2-3): `quadratic_angle_sweep.py` (grid, Brent, u, the guard
   pre-check, the budget, aggregated checks, peak count); measure and set
   `MAX_SWEEP_RHS_EVALUATIONS`; record the observed accuracy and cost for
   `SCIENTIFIC_VALIDATION.md`.
3. **API** (seam 4): request and response in `quadratic_schemas.py`, the route and
   `ModelEntry` (inputs, summary, tolerances with reasons, headline "best angle 42.98°, range
   … m, v_t … m/s", rebuild, `digest_exclude`), registry, response union, corners test,
   appended golden run, `make api-types`; derive the `best_angle_uncertainty_deg` rule by
   emulation. Run `/security-review` (new limits and inputs).
4. **Frontend** (seam 5): the panel adapter, the quadratic page, reopening, D13's wiring,
   Vitest, Playwright.
5. **Docs** (D14), then `scripts/check.sh --e2e` and a fresh-context review of the whole diff.

## Risks
- **Cost and waiting.** A Radau sweep can take ~10 s at default settings, and up to the budget
  (plus one run) otherwise; the page shows "Sweeping…" with no progress. Whether the Next.js
  proxy times out long requests was **not checked**.
- **The budget on another CPU.** Evaluation counts are deterministic on one machine, but a
  sweep near the budget could be refused (422) on another, and a stored
  `n_rhs_evaluations` (exact rule) makes "differs" on another CPU more likely than for one
  2.1 run, since it sums ~100 runs (2.1's known limitation, multiplied).
- **The stated uncertainty is pessimistic** (~1000× the observed error at defaults); it is
  labelled an estimate, but it could still confuse. Its replay rule is not derived yet (D11).
- **Local maxima.** One peak was observed on every grid measured; a second peak would make
  Brent return a local maximum. The peak-count check makes that visible, it does not fix it.
- **"Falls as drag grows" is nearly flat at large heights** (RS5), so a test there could
  fail on a legitimate tiny rise; tests use h = 0 only.
- **Duplicated grid-and-Brent logic** with `angle_sweep.py` until 2.5 (D9).
- **Learning-guide tags shift** in four files (D14), with no automatic check.
- **Test time.** The corners test and two new e2e cases add run time; not measured yet.
- **Golden re-pin side effects**, as in 2.1: on a different CPU the pin script would rewrite
  the existing entries; keep them unchanged.
- **Unverified:** whether SciPy's bounded Brent can ever evaluate a bracket end exactly (0°
  is handled without a solve either way); the Next.js timeout; the budget's final value; the
  behaviour on CI's CPU; the RS5 properties outside the measured grid; the hodograph-method
  literature (as in 2.1).

## Out of scope (awaiting the author)
- **Best angle against drag strength** (capability map, Core). A chart of θ* against
  ε = (v₀/v_t)² (and against b for linear drag). Cost: roughly one PR the size of 2.2. Each
  drag value needs a best-angle search; with continuation (bracket from the previous
  optimum, Brent only, ~10-20 runs per value) 30 values are ~450 runs, about 2-5 s with DOP853
  at default settings and 10× that with Radau, so it needs a larger budget or a coarser
  default. References already exist: RS1, RS3 (its slope at ε → 0) and RS5 (observed); linear
  drag is cheap (closed-form ranges). It might instead fall out of roadmap 2.5 ("Generic
  sweeps") as "sweep `drag_constant`, report `best_angle_deg`" at the cost of a slice there.
  **What falls out for free in 2.2:** only the weak-drag formula θ* ≈ 45° − 6.02°·ε, in the
  tests and the guide, not a feature. Decision needed: whether, and in 2.2b, 2.5 or later.
- **Drag-law comparison** (capability map, Core). Linear and quadratic results on one chart.
  Cost: one PR. It needs a **matching rule**, a modelling choice that changes the conclusion
  (equal terminal speeds, b = √(mgc); equal drag at launch, b = c·v₀; or one ball described
  both ways), and then either a cross-model overlay (a change to decision 17, which is
  same-model only) or a new combined model. Decision needed: whether, which matching rule,
  and where on the roadmap.
- Also out: sweeping any input other than the angle (2.5), animation (2.6), any change to the
  linear model, its sweep or the 2.1 model, wind, spin and lift, C_d varying with speed.

## Genuine stops found
None. Checked: no new dependency (SciPy's `minimize_scalar` and `quad`, NumPy and the stdlib
`decimal` are already used); no database migration (a new model, endpoint, registry entry
and union member are purely additive, and existing responses and digests are unchanged,
which the golden test enforces); security: a new endpoint with bounded numeric inputs through
`StrictModel`, and a work budget so one request cannot run unboundedly (reviewed with
`/security-review` in slice 3); no roadmap scope or order change (the two capability-map
items are listed above for the author, not scheduled); every claim has an independent
reference (RS1-RS4) or is labelled observed (RS5) or an estimate (u).
