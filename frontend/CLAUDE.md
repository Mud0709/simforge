# Frontend notes (loaded when work happens in `frontend/`)

- **A model's page** sits inside the shared `Workspace` layout (`src/components/`), with form
  fields declared through `spec()` (`lib/fields.ts`); it shows every number labelled by how it
  was obtained ("numerical", "exact", "formula").
- **The 1.6 wiring every model gets** (`ARCHITECTURE.md`, "Adding a new model"): the response
  union (`lib/api/models.ts`, matching `backend/.../api/outputs.py`), CSV tables
  (`lib/export/tables.ts`), reference curves (`lib/reference/overlay.ts`), stored fields
  (`lib/reference/compare.ts`), reopening (`lib/runs/pages.ts`), and a case in
  `e2e/stored-fields.spec.ts`.
- **API types are generated:** after a backend schema change run `make api-types` from the
  root (`npm run gen:api` alone only rebuilds `schema.d.ts` from the existing `openapi.json`);
  never edit `src/lib/api/openapi.json` or `schema.d.ts` by hand.
- **Checks while building** (from `frontend/`): `npx vitest run <files>`, `npm run lint`,
  `npm run format:check`, `npm run typecheck`; Playwright with `CI=1 npx playwright test`.
