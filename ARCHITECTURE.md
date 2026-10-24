# Architecture

SimForge is a **modular monolith**: one deployable backend and one frontend, with strict
internal boundaries between modules. This document records the structure and the reasoning
behind it.

## System overview

```
Browser ──► Next.js (TypeScript, :3000) ──/api/* proxy──► FastAPI (Python, :8000)
              │  UI, charts, form UX                         │  body-size guard, HTTP layer
              │                                              │  (validation, errors)
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
│   │   ├── quant/profiling/         Dataset profile: limits.py, parsing.py (bytes -> text table),
│   │   │                              inference.py (cell and column types), statistics.py,
│   │   │                              model.py (orchestration, checks), schemas.py, samples/
│   │   ├── persistence/             SQLite experiment log (stdlib sqlite3)
│   │   ├── api/                     FastAPI routes (physics, economy, quant, experiments; each
│   │   │                              model's registry entry sits next to its route),
│   │   │                              runs.py (ModelEntry + the shared run path), registry.py
│   │   │                              (every model by id), recording.py (run metadata +
│   │   │                              experiment log), errors, body_limit.py (request-size guard)
│   │   ├── config.py                Settings from SIMFORGE_* environment variables
│   │   └── main.py                  App factory
│   ├── tests/                       pytest: physics/, economy/, quant/ (reference tests), api/,
│   │                                persistence
│   └── scripts/export_openapi.py    Writes the API contract for the frontend
├── frontend/                        Next.js 16 App Router, React 19, TypeScript (strict)
│   ├── src/app/                     Routes: /, /physics/projectile, /physics/projectile/integrators,
│   │                                /economy/solow, /quant/datasets, /experiments
│   ├── src/components/              Workspace (shared layout, used by every model page),
│   │                                SolowLab/Results, ProjectileLab/Results, AngleSweepPanel,
│   │                                IntegratorLab/Results, QuantLab/Results, ChecksTable,
│   │                                NumberField, PlotlyChart, ExperimentLog
│   ├── src/lib/api/                 openapi.json + generated schema.d.ts + typed client
│   ├── src/lib/fields.ts            Schema-driven form fields for every lab (bounds and integer
│   │                                types read from openapi.json); lib/projectile and lib/economy
│   │                                list each model's fields; lib/quant encodes uploads
│   └── e2e/                         Playwright full-stack tests
├── scripts/                         setup.sh, dev.sh, check.sh (used locally and mirrored in CI)
├── .github/workflows/ci.yml         backend, frontend, api-contract, e2e jobs
├── .claude/                         Claude Code setup: skills/ (project skills, sources in
│                                    SOURCES.md) and a SessionStart hook that installs
│                                    dependencies in cloud sessions
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

Bounds are physical, not just "positive". A bound such as `mass > 0` still admits 1e-305 kg,
where the arithmetic overflows. The projectile therefore has floors (mass ≥ 1e-6 kg, speed
≥ 1e-3 m/s) and a limit on the *combination* that the physics depends on, the drag rate
`k = b/m ≤ 1e4 s⁻¹`. A test runs every corner of the allowed space and requires a result or a
422 with a reason, never a 500. Validation errors echo the rejected input back to the
client, as FastAPI does by default, except that file content (`content_base64`) is always
replaced by a note, and so are long strings in the echoed input or field location.

### 4. One source of truth for the API contract
Backend Pydantic schemas → `openapi.json` → `openapi-typescript` → `schema.d.ts`. The
frontend's types *and* its form bounds come from this file. A CI job regenerates both files
and fails if they differ from what is committed, so the frontend and backend cannot drift
apart without anyone noticing.

### 5. The experiment log stores inputs, not outputs (plus a fingerprint of the outputs)
Each saved run records validated inputs, a SHA-256 hash of their canonical JSON, the model
version, library versions and summary metrics. Time series are deliberately not stored:
models are deterministic, so the inputs together with the versions are the reproducible
record. The stdlib `sqlite3` module is used because there is one table and no ORM is
needed yet. A `schema_version` table guards against silent incompatibility.

**Run record v2 (roadmap 1.4).** Two hashes answer two different questions:
- the **input hash** says the same *question* was asked;
- the **output digest** (SHA-256 of the canonical JSON of the full response without its run
  metadata) says the same *answer* came back. JSON writes each float in its shortest exact
  form, so equal digests mean every output value is bit-identical. It is returned with every
  run, so anyone can recompute it from the response.

v2 records also store the CPU model (another processor can round the last bits differently,
which CI showed) and the git commit of the code that ran (`SIMFORGE_GIT_COMMIT` if the
deployment sets it, else the checkout's commit with `-dirty` if it has changes, else
`unknown`) and the Python implementation, plus `record_version` and `replay_of` (the run a
replay reproduced). **Migration:** a v1 log is copied to `<name>.v1.bak`, then three columns
are added in one real transaction (Python's `sqlite3` would otherwise commit before each
`ALTER TABLE`; a test shows a failed migration leaves nothing half done). Old rows are never
rewritten: they read as v1 records with no digest. A log newer than the code is refused.
**Golden runs** (`tests/api/golden_runs.json`, checked by `tests/api/test_golden_digests.py`)
pin the outputs of fixed inputs for each model version, so outputs cannot change without a
version bump. On the pinning machine the digest must match; elsewhere the summary must agree
within the declared replay tolerances. They guard against regressions; they are not evidence
of correctness.

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

### 10. One experiment-log path for every model, and a model registry
Every endpoint, in every lab, records runs through one helper (`record_run` in
`api/recording.py`). It moved there from the physics routes when the Economy Lab became the
second lab to need it. Each model hashes exactly the inputs that affect its numbers and
stores a small, model-specific summary.

Since roadmap step 1.4 each model describes itself once, as a `ModelEntry` (`api/runs.py`)
placed next to its route: how to compute it, which inputs are hashed, what summary is stored,
how the response is built, and how to **rebuild a request from stored inputs**. Every model
endpoint is one call to `execute(entry, ...)`, and `api/registry.py` lists the entries by
model id. Replay looks a stored run's model up in the registry and goes through the same
entry, so a replay asks exactly the question the original asked, computed by the same code.
The registry is a plain tuple and a lookup function, not a plugin framework; all five models
in all three labs needed it. Introducing it changed no response: every endpoint's full
response was compared byte for byte before and after. The frontend's experiment log renders a one-line
"key result" per model (step 1.5 on the roadmap replaces the per-model branches with
headlines supplied by a model registry).

### 11. One scientific workspace for every lab
`components/Workspace.tsx` lays out every model page the same way: **Parameters** on the
left; **Visualisation**, **Results**, **Assumptions** and **Validation** on the right. Each
section is a labelled region, so tests and screen readers can find it. The component only
arranges content; each model supplies its own form, charts and tables, split into one piece
per region (e.g. `ProjectileCharts`, `ProjectileValidation`, `IntegratorOrders`). It was built
for the Solow model first; in roadmap step 1.2 the projectile and integrator pages moved into
it. The only change the second real example needed: Assumptions and Validation are stacked at
full width, because validation tables (exact vs numerical, per-run inclusion decisions) did not
fit at half width. **Validation** always answers "how do we know these numbers are right?":
per-run checks for Solow, the comparison with the exact solution for the projectile, the
pre-declared fit rule and per-run evidence for the integrator study.

The workspace also owns three behaviours every page needs, so no lab can forget one:
- **Placeholders.** A page passes each region's content, or `null` before there is a result,
  plus one placeholder text per region.
- **Out-of-date results.** Each page remembers the inputs its result was computed from (one
  string of all the form's values). When the form no longer matches, the page passes a
  `staleNote` and the workspace marks Visualisation, Results and Validation. Old results stay
  visible, labelled, rather than disappearing or passing as current.
- **One short live status line.** Screen readers hear "Running…" and "Run complete. Showing run
  …", not every chart and table (the regions themselves are not live).

Shared pieces used by all three labs: `ChecksTable` (decision 12) and `AssumptionsList`.
Chart components are wrapped in `React.memo`, so typing in the form does not redraw Plotly
charts. The Parameters panel is sticky but never taller than the window; a long form scrolls
inside it.

### 12. Per-run validation is data, not decoration
A model can return `checks`: each has a value, an optional limit, a pass/fail/info status and
a *kind* (exact identity, numerical diagnostic or informational). The Validation section
renders them. They describe one run; proofs and grid evidence live in
`SCIENTIFIC_VALIDATION.md` and the test suite, and the page says so. When the dataset profile
became the second model to report checks, the `ValidationCheck` schema moved to
`core/schemas.py` (its OpenAPI name is unchanged) and the table moved from `SolowResults` to a
shared `ChecksTable` component; the Solow page renders exactly as before.

### 13. Imported datasets live for one request; their identity is a hash
An uploaded CSV is sent as base64 inside the JSON body, so it goes through the same strict
schema, OpenAPI contract and error handling as every other request. (A multipart form upload
would need another dependency and spools large files to temporary disk.) The bytes exist only
in memory while the profile is computed: they are not written to disk, the database or the
logs, and the server keeps nothing afterwards. The browser keeps the file in memory so the
user can re-profile it with different settings; reloading the page discards it.

Identity, not storage: a profile is determined by the model version, the SHA-256 of the exact
bytes and the canonicalised options (markers sorted and de-duplicated, overrides sorted).
`input_hash` covers all of them, so changed settings can never be mistaken for an earlier
result; the page also marks a result stale as soon as any setting differs from the one it was
computed with. A hash identifies bytes; it is not evidence that the data are accurate. Saving
to the experiment log is opt-in and stores only the hash, size, options and counts: no rows,
file name or column names (overrides refer to column positions). The options do include the
missing-value markers the user typed; a marker is, by definition, text that occurs in the
data, so markers should be generic tokens (`NA`, `-999`), not personal values. Replay (roadmap 1.4)
will ask for the file again and check the hash. Because there is no authentication, the
experiment log is visible to anyone using the deployment; no stronger isolation is claimed.

Parsing uses the standard `csv` module and statistics use NumPy; pandas is not needed yet
(its CSV reader pads short rows, treats strings such as "NA" as missing and guesses types by
default, all of which this feature must control explicitly). It arrives in Phase 5.

### 14. Request bodies are capped before they are read
`api/body_limit.py` refuses any request body larger than `MAX_REQUEST_BYTES` with 413: at once
if `Content-Length` says so, otherwise while counting a chunked body. The limit is derived in
`quant/profiling/limits.py`: 2 MiB of file, its base64 length (4 characters per 3 bytes,
2,796,204), plus 64 KiB for the JSON and options. The schema caps the base64 length, and the
decoded size is also checked, by the parser, because base64's 3-byte groups let that length
decode to 1 byte more. Every other endpoint's body is under a kilobyte, so they are unaffected
(a test confirms it). The guard is added before the CORS middleware, so CORS wraps it and a
413 still carries the CORS headers a browser needs to read the message.

### 15. Replay compares answers, not just questions
`api/replay.py` reruns a stored run through its registry entry (decision 10). It refuses
anything that would not be a reproduction (a changed model version, inputs that no longer
validate or hash the same, a re-supplied file whose SHA-256 differs, which is checked before
the file is read), then compares output digests. When digests are missing (v1 records) or
differ, it compares the stored summary field by field against tolerances each model declares
next to its entry, with a reason for each; a test makes sure every stored field has exactly
one rule. A saved replay is a **new** record with `replay_of` pointing to the original, so the
log stays append-only.

### 16. The experiment log is generic (roadmap 1.5)
The log page knows nothing about individual models. Each registry entry writes its own
one-line **headline** from a stored summary (computed when the log is read, so old runs get
one too; an unknown model or an older summary shape gets "—"), and says whether a replay
needs a file (`replay_needs_file`, true for an uploaded dataset). The page filters by lab,
loads 50 runs at a time, replays a run in place and links to `/<page>?run=<id>`, where the
lab page fills its form from the stored inputs without running anything. A run can carry a
**name** and a **note** (schema v3, migrated like v2: backup, one transaction). They are
labels, not part of the scientific record: `PATCH` can change only them, and the page shows
them as plain text. With no authentication, anyone using the deployment can edit labels;
deletion stays deferred because it could destroy records.

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
| GET | `/api/v1/quant/datasets/samples` | Bundled synthetic datasets |
| POST | `/api/v1/quant/datasets/profile` | Profile an uploaded CSV (base64) or a bundled sample |
| GET | `/api/v1/experiments`, `/api/v1/experiments/{run_id}` | Experiment log |
| GET | `/api/v1/experiments?lab=&limit=&offset=` | The log, newest first, with each model's one-line headline |
| PATCH | `/api/v1/experiments/{run_id}` | Set a run's name and note (nothing else can change) |
| POST | `/api/v1/experiments/{run_id}/replay` | Rerun a stored run; verdict identical / within tolerance / differs |

## Adding a new model (the intended pattern)

1. Create `backend/src/simforge/<lab>/<model>/` with pure `analytical.py`/`numerical.py`
   (or `simulation.py`), plus `schemas.py` and `model.py` (`MODEL_INFO`, `UNITS`,
   `ASSUMPTIONS`, `run()`).
2. Write reference tests *first*. List them in `SCIENTIFIC_VALIDATION.md`.
3. Add a route in `api/routes/` with the model's `ModelEntry` next to it, call
   `execute(entry, ...)` from the endpoint, and add the entry to `api/registry.py`. The
   registry test then checks that stored inputs rebuild the same computation.
4. Run `make api-types`, then build the UI in `frontend/src/components/` inside `Workspace`,
   with form fields declared through `spec()` in `lib/fields.ts`.
5. Add a chapter to the lab's learning guide (`docs/`).

## Deliberately not included (yet)
No authentication, no background job queue, no ORM or migrations framework, no
containerised deployment and no paid APIs. Each will be added only when a concrete
need appears (see ROADMAP.md).
