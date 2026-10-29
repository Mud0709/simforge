# Roadmap

SimForge is one scientific studio with **three labs**: Physics, Economy and Quant Research.
The plan builds a thin, working slice of every lab early (so the shared infrastructure is
designed against real examples from all three), then deepens each lab in turn.

**Two tracks.** Everything from "Capability map" to "Phase 7" below is **Track B, the
Advanced Simulation Studio**. An **additive** Track A, IB Foundations, is recorded at the end
of this file and in `docs/IB_FOUNDATIONS.md`. Track A adds simpler, IB-aligned simulations
alongside Track B. It does not remove, downgrade or reorder any Track B item, or postpone one
indefinitely. (Interleaving a Track A module can delay the next Track B step a little; that is
allowed.)

Rules for every phase:
- Each step is one reviewable PR that leaves the app working, with tests, an updated
  `SCIENTIFIC_VALIDATION.md` section and an updated learning guide.
- Scientific correctness, security and data integrity are requirements, not polish.
- A shared abstraction is extracted only when real models from at least two labs need it.
- Mathematical guarantees, tests and empirical evidence are labelled as such.

Legend: ✅ done · 🔜 next · ⏳ planned

---

## Capability map: what each lab will eventually contain

Tags: **Core** (on this roadmap), **Ext** (scheduled after the core), **Later** (only with a
clear purpose).

### Physics Lab
| Area | Contents |
|---|---|
| Projectile motion | ✅ linear drag (exact, adaptive and fixed-step solutions) · ✅ range against launch angle · ✅ quadratic drag (numerical, checked against the exact vertical flight, the c → 0 limit, terminal speed, the energy balance and a conserved quantity) · ✅ angle sweep for both drag laws (each law on its own page; quadratic: a grid of numerical runs with a refined best angle and an accuracy estimate) · Core: best angle against drag strength, drag-law comparison · Ext: wind |
| Oscillators | Core: simple, damped and driven harmonic oscillator, resonance curve · Ext: nonlinear pendulum (elliptic-integral period) |
| Numerical methods workbench | ✅ Euler, RK4, implicit-drag Verlet convergence study (projectile) · Core: the same workbench for any time-stepping model, symplectic Euler and Verlet, long-run energy drift, event-location error · Ext: Boris pusher |
| Collisions | Core: 1-D elastic and inelastic (restitution), 2-D discs, momentum and energy bookkeeping, animation |
| Kinetic theory | Ext (after collisions are validated): a gas built from the collision engine; pressure, temperature, Maxwell-Boltzmann distribution checked statistically |
| Orbits | Core: two-body orbits with Kepler's equation as the exact reference, conservation laws, Kepler's laws, long-run integrator comparison · Ext: Hohmann transfer, figure-eight three-body orbit |
| Charged particles | Ext: cyclotron motion and E×B drift (exact solutions) |
| Not planned | CFD, relativity, quantum mechanics (hard to validate honestly at this stage) |

### Economy Lab
| Area | Contents |
|---|---|
| Growth | ✅ Solow growth model in discrete time, with a savings-rate policy experiment |
| Short-run macro | Core: Keynesian multiplier, AD-AS (short and long run), three-equation New Keynesian model with **backward-looking** expectations (IS curve, Phillips curve, Taylor rule) and Okun's law |
| Experiments | Core: demand, supply (cost-push), monetary and fiscal shocks; impulse responses; baseline against scenario |
| Schools of thought | Core: the same shock under named assumption sets (Keynesian, Monetarist, New Classical), framed as "what follows if you assume this" |
| Sensitivity and uncertainty | Core: parameter sweeps, tornado charts, random AR(1) shocks with recorded seeds, fan charts |
| Interpretation | Core: equations shown in the UI, results labelled as illustrative model output |
| Later | Rational-expectations models (need a dedicated solver); a micro supply-and-demand market; overlaying real data imported through the Quant Lab |

### Quant Research Lab
| Area | Contents |
|---|---|
| Data | ✅ CSV upload with size limits, type detection with overrides, missing-value and duplicate report; bundled synthetic datasets with known answers · Core: cleaning as a replayable recipe · Later: public-domain samples with a clear purpose |
| Exploration | ✅ summary statistics, histograms, category counts · Core: scatter matrix, time plots |
| Statistics | Core: correlation with confidence intervals; OLS with robust standard errors, residual diagnostics (pandas for data handling, statsmodels where established implementations fit, checked against NIST certified values) |
| Time series | Core: returns, rolling volatility, decomposition, autocorrelation, stationarity tests, forecasts with prediction intervals always compared with naive baselines |
| Backtesting | Core: walk-forward engine that cannot look ahead, transaction costs, in- and out-of-sample splits, metrics with uncertainty |
| Overfitting | Core: parameter heatmaps, out-of-sample degradation, number of configurations tried, random/permutation nulls · Ext: deflated Sharpe ratio |

### Shared studio capabilities (built once)
Model registry, a common workspace layout (✅ first version), schema-driven forms (✅),
run records with model version, inputs, environment, dataset identity and seeds, replay with
a reproducibility verdict, comparison of runs, export, and per-run validation reporting.

**Reproducibility contract.** Same inputs and environment for a deterministic model:
bit-identical results. Different library versions or platform: agreement within a tolerance
each model declares in advance, with the largest difference reported. Random models record
their seed and generator. Datasets are identified by the SHA-256 of their bytes plus parsing
options (and later, the cleaning recipe).

---

## Phase 0: Foundation ✅
Scaffolds, strict schemas, experiment log, CI. Physics: projectile with linear drag (exact
vs adaptive), from-scratch integrator convergence study, range-against-angle sweep.

## Phase 1: Studio core and a walking skeleton across all three labs ✅
| Step | Outcome | Status |
|---|---|---|
| 1.1 | **Economy Lab's first model: Solow growth.** `/economy/solow` in the first version of the shared workspace (Parameters, Visualisation, Results, Assumptions, Validation); lab navigation | ✅ |
| 1.2 | **Physics moves into the workspace.** Projectile, integrator and angle-sweep pages use the same layout; exact-vs-numerical comparison shown under Validation | ✅ |
| 1.3 | **Quant Lab's first feature.** CSV upload and bundled synthetic datasets, identified by content hash (the file itself is not stored); column types with overrides, missing values, duplicates and summary statistics. Built on the standard `csv` module and NumPy; pandas arrives in Phase 5 | ✅ |
| 1.4 | **Run record v2, model registry and replay.** Migration of the experiment log; `POST /experiments/{id}/replay` with an identical / within tolerance / differs verdict (a dataset profile is replayed by supplying the file again; its SHA-256 must match) | ✅ |
| 1.5 | **Generic experiment log.** Runs by lab with model-supplied headlines; reopen a run (parameters in the URL), replay, name and annotate it | ✅ |
| 1.6 | **Comparison and export.** Pin a reference run and overlay another run of the same model, with a table of input and summary changes; recompute a stored run's series (digest-checked); export series as CSV and the run record as versioned JSON | ✅ |

Done when each lab has a real, validated feature in the same workspace and every run can be
saved, reopened, replayed, compared and exported.

## Phase 2: Physics Lab, mechanics and numerical methods ⏳
Quadratic drag (validated against the exact vertical `tanh` solution, the c → 0 limit,
terminal speed and energy balance); angle sweeps for both drag laws; simple, damped and driven
oscillators; the methods workbench for any time-stepping model (symplectic methods, energy
drift, event-location error); generic sweeps; animation.

| Step | Outcome | Status |
|---|---|---|
| 2.1 | **Quadratic drag.** Validated against the exact vertical `tanh` solution, the c → 0 limit, terminal speed and energy balance, plus the hodograph invariant and two proved bounds; `/physics/projectile/quadratic-drag` (plan and amendments: `docs/plans/ROADMAP_2_1_PLAN.md`) | ✅ |
| 2.2 | **Angle sweeps for both drag laws.** The quadratic-drag sweep `physics.projectile.quadratic_angle_sweep` on `/physics/projectile/quadratic-drag` (every point a 2.1 run; best angle by Brent with an accuracy estimate; checked against the vacuum closed form, a weak-drag first-order result and an independent integration; work budget); the linear sweep unchanged (plan and amendments: `docs/plans/ROADMAP_2_2_PLAN.md`) | ✅ |
| 2.3 | **Simple, damped and driven oscillators.** | 🔜 |
| 2.4 | **The methods workbench for any time-stepping model.** Symplectic methods, energy drift, event-location error | ⏳ |
| 2.5 | **Generic sweeps.** | ⏳ |
| 2.6 | **Animation.** | ⏳ |

Done when every item above is built and validated in the shared workspace: quadratic drag
against its references, angle sweeps for both drag laws, the three oscillators, the methods
workbench for any time-stepping model, generic sweeps and animation.

## Phase 3: Economy Lab, macro policy studio ⏳
Multiplier, AD-AS, the backward-looking three-equation NK model with Okun's law; shock
library and impulse responses; assumption sets for schools of thought; Monte Carlo runs with
seeds and fan charts; sensitivity analysis. Rational expectations stays a later extension.

## Phase 4: Physics Lab, collisions and orbits ⏳
1-D and 2-D collisions with bookkeeping and animation; two-body orbits with Kepler's
equation; long-run integrator studies. **4b:** kinetic-theory gas, only after the collision
engine is validated.

## Phase 5: Quant Research Lab, data, statistics and forecasting ⏳
Adds pandas for data handling. Cleaning recipes, exploration, correlation, OLS and diagnostics (NIST StRD references,
confidence-interval coverage simulations), time series and forecasting against baselines.

## Phase 6: Quant Research Lab, backtesting and overfitting ⏳
Walk-forward engine with a no-look-ahead guarantee test, costs, out-of-sample validation,
overfitting dashboard.

## Phase 7: Integration and visual polish ⏳
Design system, named studies, report export, Docker deployment, accessibility audit.
Performance work and a job queue only if measurement shows a need.

---

## Track A: IB Foundations (ADDITIVE) ⏳

**Additive only.** Track A is a second track, not a change of direction. Every Track B item
above stays in scope, in order and planned in full. Where a Track A module covers a topic
Track B also covers (supply and demand, collisions, oscillators, AD-AS, the multiplier, orbits,
kinetic theory, regression), the Track A module is an introductory precursor and the Track B
item remains planned unchanged.

Accessible, IB-aligned simulations (Physics HL, Economics SL with HL extensions), held to the
same standards as Track B. The syllabus mapping was checked against the official Physics guide
(first assessment 2025) and Economics guide (first assessment 2024), both read from copies the
author supplied; the author confirmed the Economics edition for their course. Verified: the
Physics themes, subtopic titles, SL/HL markers, A.1-A.5 and the skills, and Economics Units
1-4. Detailed Physics B-E content is marked "verify" and is re-checked before a module is
built. Full catalogue, syllabus mapping and sources: `docs/IB_FOUNDATIONS.md` (status:
recorded plan, nothing built yet).

| Step | Module | Possible interleaving point (optional, non-blocking) |
|---|---|---|
| A1 | Market equilibrium and elasticity (Econ 2.1-2.3, 2.5-2.6), plus a `/foundations` index | after 1.2, if practical (passed without building it; still available between later steps) |
| A2 | Momentum, impulse and collisions (Physics A.2-A.3; 1-D SL, 2-D HL) | after 1.3, if practical (passed without building it; still available between later steps) |
| A3 | Taxes, subsidies and price controls (Econ 2.7) | after 1.4, if practical |
| A4 | Kinematics graphs and forces on a slope (Physics A.1-A.2) | after 1.5, if practical |
| A5 | Measurement uncertainty and graphing (Physics Tool 3) | after 1.6, if practical |
| Later | Externalities, energy, SHM, radioactive decay, AD-AS explorer, waves, then the rest of the catalogue | between later Track B steps, if practical |

**Track B is the primary sequence and progresses independently.** The interleaving points are
suggestions, not dependencies: no Track A module is a prerequisite for any Track B step, and
Track B never waits for Track A. Track A's module order may follow the school's teaching
order; Track B's milestones and their order do not change.

