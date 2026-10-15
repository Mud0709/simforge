# Architecture

SimForge is a **modular monolith**: one deployable backend and one frontend, with strict
internal boundaries between modules. This document records the structure and the reasoning
behind it.

## System overview

```
Browser ──► Next.js (TypeScript, :3000) ──/api/* proxy──► FastAPI (Python, :8000)
              │  UI, charts, form UX                         │  HTTP layer (validation, errors)
              │  types generated from OpenAPI                ▼
              │                                        Scientific core (NumPy / SciPy)
              │                                              │  pure functions, no I/O
              │                                              ▼
              └──────────────────────────────────────  SQLite experiment log
```

## Repository layout

```
simforge/
├── backend/                         Python 3.12, managed by uv (uv.lock pins everything)
│   ├── src/simforge/
│   │   ├── core/                    Shared: StrictModel base, run metadata, hashing, errors
│   │   ├── numerics/                Model-independent methods written from scratch:
│   │   │   ├── fixed_step.py          Euler, RK4, fixed-step driver, stability functions
│   │   │   └── convergence.py         order fitting and local orders
│   │   ├── economy/solow/           Solow growth model: simulation.py (pure engine),
│   │   │                              schemas.py, model.py (assumptions, units, per-run checks)
│   │   ├── physics/projectile/      One model = one package:
│   │   │   ├── analytical.py          exact solution (pure NumPy/SciPy)
│   │   │   ├── numerical.py           ODE integration (pure NumPy/SciPy)
│   │   │   ├── model.py               orchestration + assumptions, units, model version
│   │   │   ├── schemas.py             validated request/response contract (Pydantic)
│   │   │   ├── integrator_study.py    convergence study engine (Verlet, stability, fit rule)
│   │   │   ├── integrator_model.py    study orchestration + assumptions
│   │   │   └── integrator_schemas.py  study API contract
│   │   ├── persistence/             SQLite experiment log (stdlib sqlite3)
│   │   ├── api/                     FastAPI routes (physics, economy, experiments),
│   │   │                              recording.py (run metadata + experiment log), errors
│   │   ├── config.py                Settings from SIMFORGE_* environment variables
│   │   └── main.py                  App factory
│   ├── tests/                       pytest: physics/, economy/ (reference tests), api/, persistence
│   └── scripts/export_openapi.py    Writes the API contract for the frontend
├── frontend/                        Next.js 16 App Router, React 19, TypeScript (strict)
│   ├── src/app/                     Routes: /, /physics/projectile, /physics/projectile/integrators,
│   │                                /economy/solow, /experiments
│   ├── src/components/              Workspace (shared layout), SolowLab/Results,
│   │                                ProjectileLab/Results, IntegratorLab/Results, NumberField,
│   │                                PlotlyChart, ExperimentLog
│   ├── src/lib/api/                 openapi.json + generated schema.d.ts + typed client
│   ├── src/lib/fields.ts            Schema-driven form fields for every lab (bounds and integer
│   │                                types read from openapi.json); lib/projectile and lib/economy
│   │                                list each model's fields
│   └── e2e/                         Playwright full-stack tests
├── scripts/                         setup.sh, dev.sh, check.sh (used locally and mirrored in CI)
├── .github/workflows/ci.yml         backend, frontend, api-contract, e2e jobs
└── .devcontainer/                   Reproducible cloud dev environment (Codespaces etc.)
```

## Key decisions

### 1. Modular monolith, not microservices
All three labs share validation, metadata, persistence and deployment. Separate services
would add network boundaries, deployment and versioning work without any benefit at this
scale. Boundaries are enforced by package structure instead: `physics/` never imports
`api/` or `persistence/`. A module could be extracted later if it ever needed to be.

### 2. The scientific core is pure and framework-free
`analytical.py` and `numerical.py` take a frozen dataclass of floats and return arrays. They
know nothing about HTTP, JSON or databases. This means they can be:
- tested directly and quickly (about 1 s for the full suite),
- reused from notebooks or scripts,
- reasoned about mathematically, with no hidden state.

Pydantic lives at the boundary (`schemas.py`). `model.py` is the only place that converts
between the two.

### 3. Validation at the boundary, with stated units
Every schema inherits `StrictModel`, which:
- rejects unknown fields (`extra="forbid"`), so a typo is an error rather than a silent default;
- rejects `NaN`/`±Infinity` (`allow_inf_nan=False`). This matters because Python's `json`
  parser accepts these non-standard literals;
- is immutable once validated.

Field descriptions state SI units, and every response includes a `units` map and the model's
`assumptions`. Valid inputs that the model cannot handle well (for example a stiff problem
sent to an explicit solver) raise `ModelDomainError` and produce a 422 response with an
explanation.

### 4. One source of truth for the API contract
Backend Pydantic schemas → `openapi.json` → `openapi-typescript` → `schema.d.ts`. The
frontend's types *and* its form bounds come from this file. A CI job regenerates both files
and fails if they differ from what is committed, so the frontend and backend cannot drift
apart without anyone noticing.

### 5. The experiment log stores inputs, not outputs
Each saved run records validated inputs, a SHA-256 hash of their canonical JSON, the model
version, library versions and summary metrics. Time series are deliberately not stored:
models are deterministic, so the inputs together with the versions are the reproducible
record. The stdlib `sqlite3` module is used because there is one table and no ORM is
needed yet. A `schema_version` table guards against silent incompatibility.

### 6. The browser talks only to Next.js
Next.js rewrites `/api/*` to FastAPI. This avoids CORS configuration in normal use and keeps
the backend address out of client bundles. CORS is still configurable for direct API clients.

### 7. Charts: Plotly, loaded lazily
Plotly gives zoom, pan, hover and export for free, which suits exploratory science. It needs
`window`, so `PlotlyChart` imports it inside an effect. The wrapper is about 50 lines
instead of a dependency on `react-plotly.js`.

### 8. Tooling
| Concern | Backend | Frontend |
|---|---|---|
| Dependencies | uv + `uv.lock` | npm + `package-lock.json`, exact versions |
| Lint / format | ruff | ESLint (next config), Prettier |
| Types | mypy `--strict` + pydantic plugin | `tsc` strict + `noUncheckedIndexedAccess` |
| Tests | pytest, warnings are errors | Vitest + Testing Library; Playwright E2E |

### 9. Generic numerics live apart from any model
`numerics/` holds methods that know nothing about physics (Euler, RK4, order fitting). A
problem supplies a right-hand side `f(t, y)`. Problem-specific schemes stay with their
problem; velocity Verlet with implicitly solved linear drag, for example, lives in
`physics/projectile/integrator_study.py`, because its exact implicit solve depends on the
force law. Future models, such as a harmonic oscillator or orbits, reuse `numerics/` directly.

### 10. One experiment-log path for every model
Every endpoint, in every lab, records runs through one helper (`record_run` in
`api/recording.py`). It moved there from the physics routes when the Economy Lab became the
second lab to need it. Each model hashes exactly the inputs that affect its numbers and
stores a small, model-specific summary. The frontend's experiment log renders a one-line
"key result" per model (step 1.5 on the roadmap replaces the per-model branches with
headlines supplied by a model registry).

### 11. One scientific workspace for every lab
`components/Workspace.tsx` lays out every model page the same way: **Parameters** on the
left; **Visualisation**, **Results**, **Assumptions** and **Validation** on the right. Each
section is a labelled region, so tests and screen readers can find it. The component only
arranges content; each model supplies its own form, charts and tables. It was built for the
Solow model first; roadmap step 1.2 moves the physics pages into it, and any change it needs
for physics is made then, against a real second example.

### 12. Per-run validation is data, not decoration
A model can return `checks`: each has a value, an optional limit, a pass/fail/info status and
a *kind* (exact identity, numerical diagnostic or informational). The Validation section
renders them. They describe one run; proofs and grid evidence live in
`SCIENTIFIC_VALIDATION.md` and the test suite, and the page says so.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Status and library versions |
| GET | `/api/v1/physics/projectile/info` | Model metadata |
| POST | `/api/v1/physics/projectile/simulate` | Exact vs adaptive SciPy solution |
| POST | `/api/v1/physics/projectile/integrators` | Fixed-step convergence study |
| POST | `/api/v1/physics/projectile/angle-sweep` | Range against launch angle, and the best angle |
| GET | `/api/v1/economy/solow/info` | Model metadata |
| POST | `/api/v1/economy/solow/simulate` | Solow baseline and savings-policy scenario, with per-run checks |
| GET | `/api/v1/experiments`, `/api/v1/experiments/{run_id}` | Experiment log |

## Adding a new model (the intended pattern)

1. Create `backend/src/simforge/<lab>/<model>/` with pure `analytical.py`/`numerical.py`
   (or `simulation.py`), plus `schemas.py` and `model.py` (`MODEL_INFO`, `UNITS`,
   `ASSUMPTIONS`, `run()`).
2. Write reference tests *first*. List them in `SCIENTIFIC_VALIDATION.md`.
3. Add a route in `api/routes/`. Record runs with `record_run` (`api/recording.py`).
4. Run `make api-types`, then build the UI in `frontend/src/components/` inside `Workspace`,
   with form fields declared through `spec()` in `lib/fields.ts`.
5. Add a chapter to the lab's learning guide (`docs/`).

## Deliberately not included (yet)
No authentication, no background job queue, no ORM or migrations framework, no
containerised deployment and no paid APIs. Each will be added only when a concrete
need appears (see ROADMAP.md).
