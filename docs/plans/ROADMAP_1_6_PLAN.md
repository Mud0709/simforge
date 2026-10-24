# Roadmap 1.6 plan: comparison and export (proposals, waiting for the author)

Written by the autopilot on 2026-10-24 (planning subagent, effort high; key claims re-checked
against the code). **Nothing here is built.** Each decision needs your yes, no or change
before its slice starts; reply in chat (e.g. "1.6: yes to all" or "D6: use localStorage").

**The fact that drives most choices:** full series are *not* stored. A run record keeps inputs,
summary, output digest, environment and labels (`backend/src/simforge/persistence/experiments.py:1-7`;
ARCHITECTURE decision 5). Series exist only in a live response, or after recomputing the run
from its inputs, which is how replay already works (`api/replay.py:208-239`). The digest lets a
recomputation *prove* it is bit-identical. An uploaded dataset cannot be rebuilt without its
file, and an unsaved run has no record at all.

## What 1.6 builds
On any lab page you can pin a run as the **reference run** and run again: the charts draw the
reference's curves faded under the new ones, and a small table shows which inputs changed and
how each headline number moved. You can download what a chart shows as CSV (one column per
quantity, units in the header) and any saved run's full record as JSON. All five models:
projectile, integrator study, angle sweep (Physics), Solow (Economy), dataset profile (Quant,
which exports its per-column statistics, never your file's rows).

## Decisions (recommendation in bold)
- **D1. Where exported/overlaid series come from.** (a) the page's in-memory response; (b)
  recompute stored runs and check the digest; (c) store series (breaks decision 5).
  **a + b**: use the response on screen, otherwise recompute, labelled "recomputed,
  bit-identical" or "recomputed, not bit-identical: environment differs"; 409 if the model
  version changed; an upload needs its file again, as in replay.
- **D2. Recompute API.** (a) an `include_outputs` flag on replay (mixes a verdict with a data
  download); (b) a new `POST /experiments/{id}/outputs` → `{original_run_id, digest_match,
  response}`, never saving. **b**, with replay's refusal checks moved into one shared helper so
  both routes refuse the same cases.
- **D3. Where CSV is made.** (a) server `text/csv` (outside the typed client; can't serve
  unsaved runs or in-memory uploads); (b) client, a per-model `exportTables(response)` and a
  shared `toCsv()`. **b**, the only option covering unsaved runs and uploads.
- **D4. CSV format.** Wide tables, shared x column, headers like `t [s]` from the response's
  units; numbers written as shortest round-trip (exact for doubles); `null` and shorter series
  → empty cells. **Plain RFC 4180, no `#` comment lines**; provenance in the filename
  (`<model>_<run8>_<table>.csv`) and in the JSON export. Alternative: metadata lines (carry
  provenance, break naive parsers).
- **D5. JSON export.** (a) dump the stored record as-is (no contract); (b) a versioned
  `RunExport {export_version: 1, exported_at, record}` served by
  `GET /experiments/{id}/export`. **b**, so a future import or report export can validate it.
  Record only, no series. Unsaved runs: "save first".
- **D6. Pinning the reference.** React state (lost on reload), URL `?ref=<run_id>`,
  localStorage, or a database flag (schema v4, global for everyone). **URL `?ref=`** (survives
  reload, mirrors `?run=`), plus in-memory pinning for an unsaved run, labelled as lost on
  reload.
- **D7. Overlay scope.** (a) same model only; (b) across models with matching series and
  units; (c) anything. **a**, with a warning when versions differ; data kept as named series +
  units so (b) can come later. Dataset profile: summary table only, no overlaid charts.
- **D8. What the comparison shows.** (a) curves only; (b) curves + input diff + summary diff
  (original, new, absolute and relative change); (c) (b) with replay-tolerance verdicts.
  **b**: replay tolerances measure numerical reproducibility, not scientific significance, so
  "within tolerance" between two *different* scenarios would mislead.
- **Safety (not a choice, a requirement).** String cells starting `= + - @ tab CR` get a `'`
  prefix (spreadsheet formula injection), never numeric cells (negatives start with `-`).
  Quant column names come from the user's file, so they need it; names and notes never go in
  CSVs or filenames. Sizes are already bounded by existing input limits.

## Slices (test-first, one commit each)
1. Backend recompute (D1, D2): shared refusal helper, `POST /experiments/{id}/outputs`; tests
   for digest match, 409, 422, nothing saved; `make api-types`.
2. JSON export (D5): schema and route; round-trip and 404 tests.
3. CSV export in the client (D3, D4, safety): `toCsv`, `exportTables` for all five models,
   download buttons; Vitest for units, number round-trip, nulls, ragged columns, injection.
4. Pin and overlay (D6, D7): `?ref=`, faded reference traces, version warning. Needs 1.
5. Comparison table (D8), a Playwright pin → run → overlay → export test, then docs
   (ARCHITECTURE decision 17, SCIENTIFIC_VALIDATION, README, ROADMAP, learning guides).

## Risks and out of scope
- **Naming:** Solow already calls its two paths "baseline" and "scenario"
  (`frontend/.../SolowResults.tsx:12-13, 53`), hence "reference run".
- Recomputing an integrator study may be slow; not measured yet.
- A projectile reference with a different flight time has a different time grid: overlay
  works, point-by-point subtraction is left out.
- Unverified assumptions: Plotly's built-in PNG download is enough for images; large
  responses pass the frontend proxy fine.
- Out of scope: storing series, comparing more than two runs, cross-model overlay, ZIP
  bundles, exporting preview rows, re-importing exports, the Phase 7 report export.
