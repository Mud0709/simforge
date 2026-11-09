# Backend notes (loaded when work happens in `backend/`)

The root `CLAUDE.md` Standards apply in full; these are the backend's working rules.

- **Adding a model** (`ARCHITECTURE.md`, "Adding a new model"): a package
  `src/simforge/<lab>/<model>/` with pure `analytical.py`/`numerical.py`, then `schemas.py`
  and `model.py` (`MODEL_INFO`, `UNITS`, `ASSUMPTIONS`, `run()`); a route module in
  `api/routes/` with its `ModelEntry`, called through `execute(entry, ...)`, and the entry in
  `api/registry.py` (the registry test then checks stored inputs rebuild the computation).
  Golden-run cases are appended to `tests/api/test_registry.py`, never inserted.
- **Tests first, against independent references** (closed forms, limits, invariants,
  high-precision `decimal`, independent integrations), never the code's own output; list
  them in `SCIENTIFIC_VALIDATION.md`. Use `tests/approx.py` `rel_approx`: `pytest.approx`
  adds abs=1e-12 by default and silently loosens tolerances. Write last-bit bounds in ε, since
  CI's CPU can differ in the last bit. Justify every tolerance in a comment.
- **Inputs:** Pydantic schemas validate at the boundary, reject non-finite values and state
  units; model guards raise `ModelDomainError` before any solve, saying what to change.
- **After changing a schema:** `make api-types` and commit the regenerated
  `frontend/src/lib/api/openapi.json` and `schema.d.ts`.
- **Checks while building** (from `backend/`): `uv run pytest <test files> -q`,
  `uv run ruff check . && uv run ruff format --check .`, `uv run mypy`.
