import { expect, test } from "@playwright/test";

import type { ModelResponse } from "@/lib/api/client";
import { inputFields, summaryFields } from "@/lib/reference/compare";

// The comparison table rebuilds, in the browser, the inputs and summary a run record stores
// (`inputs=` and `summary=` in backend/src/simforge/api/routes/). This guards that copy
// against drift: for each model, one real run is saved through the real API, and the fields
// the browser derives from the response must equal the stored record's, flattened with dots
// as backend/src/simforge/api/replay.py `flatten` does. Both sides come from the same run on
// the same machine, so equality is exact (JSON numbers round-trip doubles exactly). The
// inputs are values no other test uses, and each record is read back by its own run id.
const API = "http://127.0.0.1:8000/api/v1";

/** Python's `flatten` in api/replay.py: nested objects become dotted names, lists stay. */
function flatten(d: Record<string, unknown>, prefix = ""): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(d)) {
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, flatten(value as Record<string, unknown>, `${prefix}${key}.`));
    } else {
      out[`${prefix}${key}`] = value;
    }
  }
  return out;
}

const upload = Buffer.from("id,score,note\n1,3.5,a\n2,,b\n2,,b\nx,4,=c\n").toString("base64");

const CASES: [string, string, Record<string, unknown>][] = [
  [
    "physics.projectile",
    "/physics/projectile/simulate",
    { parameters: { drag_coefficient: 0.37, launch_angle_deg: 33 }, n_samples: 57 },
  ],
  [
    "physics.projectile.integrators",
    "/physics/projectile/integrators",
    { dt_values: [0.08, 0.04, 0.02], methods: ["euler", "rk4"] },
  ],
  [
    "physics.projectile.angle_sweep",
    "/physics/projectile/angle-sweep",
    { parameters: { drag_coefficient: 0.23, launch_angle_deg: 17 }, n_angles: 23 },
  ],
  [
    "economy.solow",
    "/economy/solow/simulate",
    { policy: { policy_year: 7, new_savings_rate: 0.27 }, horizon_years: 33 },
  ],
  [
    "quant.dataset_profile (sample)",
    "/quant/datasets/profile",
    { source: { kind: "sample", sample_id: "messy_survey" }, options: { missing_markers: ["?"] } },
  ],
  [
    "quant.dataset_profile (upload)",
    "/quant/datasets/profile",
    {
      source: { kind: "upload", content_base64: upload },
      options: { column_types: [{ column: 0, type: "categorical" }] },
    },
  ],
];

for (const [name, path, body] of CASES) {
  test(`${name}: the comparison's fields equal the stored record's`, async ({ request }) => {
    const run = await request.post(`${API}${path}`, { data: { ...body, save_experiment: true } });
    expect(run.ok(), await run.text()).toBe(true);
    const response = (await run.json()) as ModelResponse;
    expect(response.metadata.experiment_saved).toBe(true);

    const stored = await request.get(`${API}/experiments/${response.metadata.run_id}`);
    expect(stored.ok()).toBe(true);
    const record = (await stored.json()) as {
      inputs: Record<string, unknown>;
      summary: Record<string, unknown>;
    };

    const summary = flatten(record.summary);
    expect(Object.keys(summary).length).toBeGreaterThan(0);
    expect(summaryFields(response)).toEqual(summary);
    expect(inputFields(response)).toEqual(flatten(record.inputs));
  });
}
