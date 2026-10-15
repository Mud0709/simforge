# Roadmap

Ordered by dependency and learning value. Each milestone ends with tests, an updated
`SCIENTIFIC_VALIDATION.md` section and a working UI. Nothing is marked done until its
checks pass in CI.

## ✅ Milestone 0: Foundation
- Backend/frontend scaffolds, strict schemas, experiment log, CI, devcontainer.
- Demonstration model: projectile motion with linear drag (exact vs numerical).

## Milestone 1: Physics Lab
1. **Quadratic drag projectile** (`F = −c|v|v`). There is no closed form, so validation uses
   limits (c → 0 matches vacuum), the energy-balance invariant, terminal velocity
   `√(mg/c)`, and a grid-convergence study. This is the first model where the numerical
   result *is* the answer, so it needs an explicit error estimate.
2. **Reproducibility replay.** Add `POST /experiments/{id}/replay`: re-run the stored inputs
   and report whether the summary matches bit-for-bit, or by how much it differs if the
   library versions have changed.
3. **Parameter sweeps.** Vary one input over a range (e.g. angle 0–90°) and plot a metric,
   such as the optimal launch angle as a function of drag.
4. **Fixed-step integrators written from scratch.**
   - ✅ Euler, RK4 and velocity Verlet (implicit linear drag) on the projectile, with
     log-log convergence plots, a pre-declared fit rule and stability boundaries
     (`physics.projectile.integrators`).
   - ⏳ Symplectic Euler and standard velocity Verlet on a **harmonic oscillator**:
     long-time energy drift, where symplectic methods have a real, testable advantage.
   - ⏳ Errors in landing time and range for fixed-step methods, with an analysis of
     event-location error.
5. **Collisions.** 1-D elastic and inelastic collisions with a coefficient of restitution.
   Momentum conservation is the invariant to test.
6. **Orbital mechanics.** The two-body problem. Validate against Kepler's laws and
   conservation of energy and angular momentum, and compare RK45 with Verlet over many orbits.

## Milestone 2: Economy Lab
1. **Model framework.** Discrete-time dynamic models with explicit equations shown in the
   UI, named parameters with units (% per year, index points) and baseline-vs-shock
   comparison.
2. **First model: a three-equation New Keynesian model** (IS curve, Phillips curve, Taylor
   rule) in a transparent backward-looking form. Validate the steady state analytically and
   check stability conditions such as the Taylor principle.
3. **Policy experiments.** Interest-rate shocks, fiscal changes and supply shocks, shown as
   impulse responses for output gap, inflation and unemployment (via Okun's law).
4. **Clear labelling** of every result as *illustrative model output*, not a forecast.

## Milestone 3: Quant Research Lab
1. **CSV import.** Size limits, schema inference, missing-value report and type checking.
   No network data sources that need credentials.
2. **Regression** with statsmodels: OLS with robust standard errors, diagnostics (residual
   plots, heteroskedasticity tests) and confidence intervals displayed with their meaning.
3. **Hypothesis tests.** t-tests, a bootstrap with recorded seeds, and permutation tests.
   Validate against known distributions and published worked examples.
4. **Reproducible experiments.** Store a dataset hash, seed, code version and parameters,
   and show that re-running reproduces the result.

## Cross-cutting (as needed)
- Docker Compose for one-command deployment.
- Units handling (e.g. `pint`) if models start mixing unit systems.
- Database migrations (Alembic) when the schema first changes.
- Performance work only after profiling shows a need, for example vectorised sweeps.
- Accessibility audit (axe) in the E2E suite.
