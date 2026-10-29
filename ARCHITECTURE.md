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
│   │   │   ├── integrator_schemas.py  study API contract
│   │   │   ├── quadratic_reference.py quadratic drag: exact vertical flight, terminal speed,
│   │   │   │                            hodograph invariant, proved bounds (roadmap 2.1)
│   │   │   ├── quadratic_numerical.py quadratic drag ODE solve (state x, y, vx, vy, W)
│   │   │   ├── quadratic_model.py     guard, references, diagnostics, per-run checks
│   │   │   ├── quadratic_angle_sweep.py quadratic-drag angle sweep: a grid of 2.1 runs,
│   │   │   │                            Brent refinement, accuracy estimate, work budget,
│   │   │   │                            aggregated checks (roadmap 2.2)
│   │   │   └── quadratic_schemas.py   quadratic-drag API contract and input rules (both
│   │   │                                quadratic models)
│   │   ├── quant/profiling/         Dataset profile: limits.py, parsing.py (bytes -> text table),
│   │   │                              inference.py (cell and column types), statistics.py,
│   │   │                              model.py (orchestration, checks), schemas.py, samples/
│   │   ├── persistence/             SQLite experiment log (stdlib sqlite3)
│   │   ├── api/                     FastAPI routes (physics, economy, quant, experiments; each
│   │   │                              model's registry entry sits next to its route),
│   │   │                              runs.py (ModelEntry + the shared run path), registry.py
│   │   │                              (every model by id), recording.py (run metadata +
│   │   │                              experiment log), errors, body_limit.py (request-size guard),
│   │   │                              rerun.py (the refusals shared by replay and recompute),
│   │   │                              replay.py, outputs.py (recomputed outputs, roadmap 1.6)
│   │   ├── config.py                Settings from SIMFORGE_* environment variables
│   │   └── main.py                  App factory
│   ├── tests/                       pytest: physics/, economy/, quant/ (reference tests), api/,
│   │                                persistence
│   └── scripts/export_openapi.py    Writes the API contract for the frontend
├── frontend/                        Next.js 16 App Router, React 19, TypeScript (strict)
│   ├── src/app/                     Routes: /, /physics/projectile, /physics/projectile/integrators,
│   │                                /physics/projectile/quadratic-drag, /economy/solow,
│   │                                /quant/datasets, /experiments
│   ├── src/components/              Workspace (shared layout, used by every model page),
│   │                                SolowLab/Results, ProjectileLab/Results, AngleSweepPanel
│   │                                (the shared SweepPanel and a per-model SweepAdapter; the
│   │                                linear adapter), QuadraticAngleSweepPanel (the quadratic
│   │                                adapter and its Validation block),
│   │                                IntegratorLab/Results, QuadraticDragLab/Results,
│   │                                QuantLab/Results, ChecksTable,
│   │                                NumberField, PlotlyChart, ExperimentLog; the reference run
│   │                                and export pieces: useReferenceRun, ReferenceRunPanel,
│   │                                ComparisonTable, CsvDownloads
│   ├── src/lib/api/                 openapi.json + generated schema.d.ts + typed client;
│   │                                models.ts narrows a response to one model by its id
│   ├── src/lib/export/              csv.ts (RFC 4180 writer, formula guard), tables.ts (what
│   │                                each model exports as CSV)
│   ├── src/lib/reference/           overlay.ts (a reference run's curves per chart),
│   │                                compare.ts (input and summary differences)
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

### 17. Comparison and export (roadmap 1.6)
A lab page can pin a run as its **reference run**: the charts draw the reference's curves
faded under the new run's, and a table shows what changed. Any chart's data downloads as CSV,
and any saved run's record as JSON. The plan and its decisions (D1-D8) are in
`docs/plans/ROADMAP_1_6_PLAN.md`; the choices that shape the code are:

- **Series are recomputed, not stored, and the digest says whether the recomputation is
  exact.** Decision 5 stands: the log keeps no curves. `POST /experiments/{id}/outputs`
  (`api/outputs.py`) rebuilds the stored request, runs it through the same registry entry as
  the original, saves nothing, and returns `{original_run_id, digest_match, response}`.
  `digest_match` is true when the new output digest equals the stored one (every value
  bit-identical), false when both exist and differ, and null for a v1 record with no digest.
  The page labels a recomputed reference "recomputed, bit-identical", "recomputed, not
  bit-identical (cause not checked; usually another CPU or library version)" or "cannot be
  checked". The response is a union of the six models' responses, told apart by
  `model.id` (adding a literal field to tell them apart would have changed every digest).
- **One refusal helper for every rerun.** Replay and recompute both start with
  `prepare_rerun` (`api/rerun.py`), so they refuse exactly the same cases with the same
  status and message (unknown model 422, changed model version 409, stored inputs no longer
  valid 422, an uploaded file missing or different 422, checked before it is read); a test
  sends the same bad cases to both routes. Both then pass the stored input hash to
  `execute_run`, which refuses (409) a rebuilt request that no longer hashes the same.
- **CSV is made in the browser.** `lib/export/tables.ts` turns each model's response into
  wide tables (one column per quantity, `name [unit]` headers from the response's own `units`
  map), and `lib/export/csv.ts` writes them as plain RFC 4180 (comma, CRLF, quoting) with each
  number in its shortest round-trip form. Only the browser has an unsaved run or an uploaded
  file's profile, so a server-side CSV route could not serve those. Provenance lives in the
  filename, `<model>_<first 8 characters of the run id>_<table>.csv`, not in comment lines,
  which break ordinary CSV readers. The dataset profile exports its per-column statistics,
  never the file's rows.
- **The CSV formula guard.** Text that starts with `=`, `+`, `-`, `@`, a tab or a carriage
  return gets a leading `'`, so a spreadsheet shows it as text instead of running it as a
  formula (CSV or formula injection). Headers are guarded too, because Quant column names come
  from the user's file. Numbers are never prefixed: a negative number starts with `-`, and a
  number is written by the code, not taken from the user. Run names and notes never appear in
  CSVs or filenames.
- **A versioned JSON export.** `GET /experiments/{id}/export` returns `RunExport
  {export_version: 1, exported_at, record}`, where `record` is exactly what
  `GET /experiments/{id}` shows, as a download named `<model>_<run8>.json`. The version lets a
  future import or report check what it reads. It holds the record only, no series; an
  unsaved run has no record to export.
- **The reference run lives in the URL.** Pinning a saved run sets `?ref=<run_id>` (like
  `?run=` for reopening), so a reload, or a copied link, recomputes it from the log. An unsaved
  run, or a profile of an uploaded file (whose recomputation needs the file), is held in the
  tab's memory only and labelled as lost on reload. Not a database flag: a pinned run is one
  person's working choice, and with no authentication a flag would be global for everyone.
  A refused reference (409, 422, 404) is shown as a message and the page works without one.
- **Same-model overlay only.** `lib/reference/overlay.ts` keeps each model's curves as named
  series with units, and draws a reference only over runs of the same model, with a warning
  when the model versions differ. The dataset profile is compared in the table only. Named
  series with units leave room for a later cross-model overlay.
- **A comparison without verdicts.** `ComparisonTable` lists the inputs that differ and,
  for every stored summary value, the reference value, the new value, the change
  (new − reference) and the relative change ((new − reference) / |reference|, shown as "—"
  when the reference is 0). It says nothing about whether a change matters: replay
  tolerances measure whether a recomputation reproduced a run, not whether two different
  scenarios differ meaningfully.
- **A drift check for the copied field lists.** The comparison rebuilds, in the browser,
  the inputs and summary a run record stores (`lib/reference/compare.ts`). The Playwright test
  `e2e/stored-fields.spec.ts` saves one real run per model (two for the dataset profile) and
  requires the browser's fields to equal the stored record's exactly, so a change to what the
  backend stores cannot silently desynchronise the table.

On the page, the reference run is one more `Workspace` section, "Reference run", above
Visualisation; the CSV buttons sit in each model's Results (the angle sweep's in its own panel),
and the experiment log has an "Export JSON" link per run.

### 18. Quadratic drag is a new model, not an option (roadmap 2.1)
`physics.projectile.quadratic_drag` v1.0.0 has its own parameters, endpoint, registry entry,
page and four modules (`quadratic_reference.py`, `quadratic_numerical.py`,
`quadratic_model.py`, `quadratic_schemas.py`); the plan and its amendments are in
`docs/plans/ROADMAP_2_1_PLAN.md`. The choices that shape the code:

- **A new model, because of input hashes and replay.** The linear model, the integrator study
  and the angle sweep share `ProjectileParameters` and store it as dumped. A `drag_law` field
  would enter every rebuilt request, so every stored run of those three models would hash
  differently and replay would refuse it (409); their responses and digests would change too,
  forcing three version bumps for unchanged physics. A new model is purely additive, and the
  golden test shows the existing digests unchanged. It reuses `SolverSettings` and
  `NumericalResult` unchanged; the cost is about 40 lines of event logic copied from
  `numerical.py`, left for the methods workbench (roadmap 2.4) to share.
- **A guard from a proved bound, not from an exact answer.** With no exact flight time, the
  integration is capped at twice a proved flight-time bound, and explicit methods are refused
  (422, with the reason) when a proved bound on the drag time `S = ∫κ|v| dt` exceeds 1e4,
  the linear model's limit. `S` measures the cost of an explicit method directly; the plan's
  `κ·max(v₀, v_t)·T_bound` multiplied two loose bounds and refused runs that finish. Radau
  has no drag-time limit.
- **Input rules where the measurements said so.** Besides the linear model's field bounds and
  a drag-rate limit `κ·max(v₀, v_t) ≤ 1e4 s⁻¹`, the request requires
  `atol ≤ 0.01·min(v₀, v_t)` (above it the velocity is not error-controlled and runs became
  very slow) and a drag-free flight of at least 1 µs (the landing cannot be resolved below
  it). Both live on this model's request, not on the shared `SolverSettings`, so the linear
  model is untouched.
- **Per-run checks and replay rules share their scales.** The energy balance and the
  hodograph invariant are checked on every run against `1e4 × accuracy + 1e-9` (empirical),
  and the replay tolerances for the same residuals use the same accuracy scales, with rtol
  floored at 1e-10.

### 19. The quadratic-drag angle sweep is a new model built from 2.1 runs (roadmap 2.2)
`physics.projectile.quadratic_angle_sweep` v1.0.0 lives in `quadratic_angle_sweep.py`, with
its request and response appended to `quadratic_schemas.py` and its route and `ModelEntry`
appended to `api/routes/physics.py`; the plan and its amendments are in
`docs/plans/ROADMAP_2_2_PLAN.md`. The choices that shape the code:

- **A new model, for the reason of decision 18.** A `drag_law` field on the linear sweep's
  request would change the input hash of every stored linear sweep, and a quadratic sweep
  needs inputs the linear one lacks (`drag_constant` in kg/m, the solver settings). The linear
  model, its sweep and the 2.1 model keep their versions and digests; the golden test shows it.
- **Each point is a call to the 2.1 model, not a new solver.** The sweep calls
  `quadratic_model.run` per angle, so every point is bit-identical to a single 2.1 run on the
  same machine and gets the same guard, events and checks; no 2.1 code changed. The 2.1
  checks are aggregated per check id over every run (passed only if all passed; the run
  closest to its limit is reported with its angle). The ~25 lines of grid-and-Brent logic are
  repeated from `angle_sweep.py` rather than shared, until generic sweeps (roadmap 2.5) give a
  shared layer more than two users.
- **A work budget in right-hand-side evaluations.** A sweep is ~100 numerical solves, so it is
  capped at 3e5 evaluations in total (a server constant, not a request field), checked after
  each run, and refused with a 422 that says what to change. A count is reproducible on one
  machine; a timeout is not. The value was measured against the Next.js proxy's 30 s timeout.
  The stiffness guard runs at every grid angle before any solve, and the 2.1 input rules are
  checked once, at the sweep's smallest flown angle.
- **An accuracy estimate, labelled as one.** The response carries `best_angle_uncertainty_deg`
  (`u = 2√(ε_R/K)`, `null` with a reason at an edge), and its replay rule is derived from how
  `u` is computed; the best angle replays within `max(1e-5°, u)`.
- **One panel, two adapters.** `AngleSweepPanel.tsx` holds a generic `SweepPanel` and a
  `SweepAdapter` interface (run function, labels, optional drag-free curve, extra stats, an
  optional angles field); the linear page's adapter keeps its behaviour, and the quadratic
  page's (`QuadraticAngleSweepPanel.tsx`) adds the estimate, the dashed drag-free curve, the
  peak count and a number-of-angles field. No cross-model overlay (decision 17 stays
  same-model only).

## API endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/v1/health` | Status and library versions |
| GET | `/api/v1/physics/projectile/info` | Model metadata |
| POST | `/api/v1/physics/projectile/simulate` | Exact vs adaptive SciPy solution |
| POST | `/api/v1/physics/projectile/integrators` | Fixed-step convergence study |
| POST | `/api/v1/physics/projectile/angle-sweep` | Range against launch angle, and the best angle |
| POST | `/api/v1/physics/projectile/quadratic-drag/simulate` | Quadratic drag: adaptive SciPy solution with the exact vertical flight, vacuum comparison, diagnostics and per-run checks |
| POST | `/api/v1/physics/projectile/quadratic-drag/angle-sweep` | Range against launch angle with quadratic drag (one 2.1 run per angle), the refined best angle with an accuracy estimate, the exact drag-free curve and optimum, and checks over every run |
| GET | `/api/v1/economy/solow/info` | Model metadata |
| POST | `/api/v1/economy/solow/simulate` | Solow baseline and savings-policy scenario, with per-run checks |
| GET | `/api/v1/quant/datasets/samples` | Bundled synthetic datasets |
| POST | `/api/v1/quant/datasets/profile` | Profile an uploaded CSV (base64) or a bundled sample |
| GET | `/api/v1/experiments`, `/api/v1/experiments/{run_id}` | Experiment log |
| GET | `/api/v1/experiments?lab=&limit=&offset=` | The log, newest first, with each model's one-line headline |
| PATCH | `/api/v1/experiments/{run_id}` | Set a run's name and note (nothing else can change) |
| POST | `/api/v1/experiments/{run_id}/replay` | Rerun a stored run; verdict identical / within tolerance / differs |
| POST | `/api/v1/experiments/{run_id}/outputs` | Recompute a stored run's full response, with whether it is bit-identical; saves nothing |
| GET | `/api/v1/experiments/{run_id}/export` | The run record as a versioned JSON download (`export_version: 1`) |

## Adding a new model (the intended pattern)

1. Create `backend/src/simforge/<lab>/<model>/` with pure `analytical.py`/`numerical.py`
   (or `simulation.py`), plus `schemas.py` and `model.py` (`MODEL_INFO`, `UNITS`,
   `ASSUMPTIONS`, `run()`).
2. Write reference tests *first*. List them in `SCIENTIFIC_VALIDATION.md`.
3. Add a route in `api/routes/` with the model's `ModelEntry` next to it, call
   `execute(entry, ...)` from the endpoint, and add the entry to `api/registry.py`. The
   registry test then checks that stored inputs rebuild the same computation.
4. Run `make api-types`, then build the UI in `frontend/src/components/` inside `Workspace`,
   with form fields declared through `spec()` in `lib/fields.ts`. Add the model to the
   response union in `api/outputs.py` and `lib/api/models.ts`, give it CSV tables
   (`lib/export/tables.ts`), reference curves (`lib/reference/overlay.ts`) and its stored
   fields (`lib/reference/compare.ts`), and add a case to `e2e/stored-fields.spec.ts`.
5. Add a chapter to the lab's learning guide (`docs/`).

## Deliberately not included (yet)
No authentication, no background job queue, no ORM or migrations framework, no
containerised deployment and no paid APIs. Each will be added only when a concrete
need appears (see ROADMAP.md).
