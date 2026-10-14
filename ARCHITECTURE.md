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
│   │   ├── physics/projectile/      One model = one package:
│   │   │   ├── analytical.py          exact solution (pure NumPy/SciPy)
│   │   │   ├── numerical.py           ODE integration (pure NumPy/SciPy)
│   │   │   ├── model.py               orchestration + assumptions, units, model version
│   │   │   ├── schemas.py             validated request/response contract (Pydantic)
│   │   │   ├── integrator_study.py    convergence study engine (Verlet, stability, fit rule)
│   │   │   ├── integrator_model.py    study orchestration + assumptions
│   │   │   └── integrator_schemas.py  study API contract
│   │   ├── persistence/             SQLite experiment log (stdlib sqlite3)
│   │   ├── api/                     FastAPI routes, dependencies, error handlers
│   │   ├── config.py                Settings from SIMFORGE_* environment variables
│   │   └── main.py                  App factory
│   ├── tests/                       pytest: physics/ (reference tests), api/, persistence
│   └── scripts/export_openapi.py    Writes the API contract for the frontend
├── frontend/                        Next.js 16 App Router, React 19, TypeScript (strict)
│   ├── src/app/                     Routes: /, /physics/projectile, /physics/projectile/integrators,
│   │                                /experiments
│   ├── src/components/              ProjectileLab/Results, IntegratorLab/Results, NumberField,
│   │                                PlotlyChart, ExperimentLog
│   ├── src/lib/api/                 openapi.json + generated schema.d.ts + typed client
│   ├── src/lib/projectile/fields.ts Form fields; bounds read from openapi.json
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
Both projectile endpoints record runs through one helper (`_record_run` in
`api/routes/physics.py`). Each model hashes exactly the inputs that affect its numbers and
stores a small, model-specific summary. The frontend's experiment log renders a one-line
"key result" per model.

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Status and library versions |
| GET | `/api/v1/physics/projectile/info` | Model metadata |
| POST | `/api/v1/physics/projectile/simulate` | Exact vs adaptive SciPy solution |
| POST | `/api/v1/physics/projectile/integrators` | Fixed-step convergence study |
| GET | `/api/v1/experiments`, `/api/v1/experiments/{run_id}` | Experiment log |

## Adding a new model (the intended pattern)

1. Create `backend/src/simforge/<lab>/<model>/` with pure `analytical.py`/`numerical.py`
   (or `simulation.py`), plus `schemas.py` and `model.py` (`MODEL_INFO`, `UNITS`,
   `ASSUMPTIONS`, `run()`).
2. Write reference tests *first*. List them in `SCIENTIFIC_VALIDATION.md`.
3. Add a route in `api/routes/`. Persist through `ExperimentRepository`.
4. Run `make api-types`, then build the UI in `frontend/src/components/`.

## Deliberately not included (yet)
No authentication, no background job queue, no ORM or migrations framework, no
containerised deployment and no paid APIs. Each will be added only when a concrete
need appears (see ROADMAP.md).
