# Roadmap 2.4: inputs recorded before planning

Not a plan: 2.4 gets its reviewed plan (autopilot skill, step 3) when it becomes the 🔜 step.
This file holds decisions and findings that 2.4's plan must take in, so they are not lost.

## 1. Per-run checks for the three Phase 0 physics models (review 2026-11-10, finding 7)
**Gap.** `physics.projectile`, `physics.projectile.integrators` and
`physics.projectile.angle_sweep` return no `checks` list; every later model does
(ARCHITECTURE decision 12). Their Validation panels show the exact-vs-numerical comparison
instead, so nothing is wrong, but the three pages cannot show a verdict or be aggregated the
way the others are.

**Why 2.4 and not now.** 2.4 moves the integrators onto a shared stepping and event layer and
touches all three models anyway (the duplicated event logic noted in 2.1 and 2.2). Adding
`checks` changes their responses, so it needs a version bump and re-pinned golden digests:
one bump per model, done once, together with 2.4's own output changes.

**Proposed checks (each from a quantity the model already computes).**
| Model | Check | Kind | Threshold |
|---|---|---|---|
| projectile | flight time, range, max height against the exact solution | numerical diagnostic | to be measured on a grid, form `F (rtol + atol/scale) + floor` as in 2.1 |
| projectile | energy balance KE + PE + W = E0 over the step nodes | numerical diagnostic | measured, as 2.1 |
| integrators | fitted order within 0.1 of theory, for each method with a fit | numerical diagnostic | 0.1 (the tests' tolerance) |
| integrators | velocity error = k x position error for Euler and RK4 (linear invariant) | exact identity | rounding-sized, measured |
| integrators | number of points in each fit; runs excluded as unstable | informational | none |
| angle sweep | interior peaks on the grid (expected 1) | numerical diagnostic | 1, as the quadratic sweep |
| angle sweep | drag never increases the best range (vs the vacuum closed form) | exact identity | 0 violations |

**Rules to carry over.** A threshold that allows an error above 100% gives no verdict
(`passed = null`), as in quadratic drag v1.0.1 and the oscillator. Thresholds are measured on
a stated grid and recorded in SCIENTIFIC_VALIDATION.md with the machine; factors are 1-2-5
values at least 10x the worst need.

**Acceptance (for the slice that builds this).** Each model's default run shows its checks and
all pass; a planted error (wrong drag sign, as in the existing mutation tests) fails at least
one; the corners tests still return a result or an explained 422; versions bumped to 1.1.0
and the three golden entries re-pinned; frontend pages render the shared `ChecksTable`.

**Open for the author.** Whether the exact-vs-numerical comparison table stays alongside the
checks (recommended: yes, it shows the numbers; the checks give the verdict).

## 2. Also waiting for 2.4 (already recorded elsewhere)
- The landing-event logic duplicated between the linear and quadratic solvers (~40 lines;
  SCIENTIFIC_VALIDATION, quadratic drag, limitations).
- Symplectic methods, energy drift and event-location error (ROADMAP 2.4).
