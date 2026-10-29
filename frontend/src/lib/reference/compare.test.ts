/**
 * The reference run's comparison table (roadmap 1.6, D8 option b): which inputs differ, and
 * how each headline summary value moved. Every expected value below is worked by hand from
 * the small fixtures here, never taken from the code under test. The summary field names are
 * those the backend stores in a run record (`summary=` in backend/src/simforge/api/routes/),
 * flattened with dots the way `flatten` in backend/src/simforge/api/replay.py does.
 */
import type { ModelResponse } from "@/lib/api/client";
import PROFILE from "@/components/fixtures/messySurveyProfile.json";
import {
  allNumbersEqual,
  compareRuns,
  inputDiff,
  inputFields,
  summaryDiff,
  summaryFields,
} from "./compare";

const as = (r: unknown) => r as ModelResponse;
const meta = (run_id: string) => ({ run_id, experiment_saved: true });

function solow(o: {
  k0?: number;
  k1?: number;
  golden?: number;
  halfLife?: number;
  finalK?: number;
  newSavings?: number;
}) {
  return as({
    model: { id: "economy.solow", version: "1.0.0", name: "Solow" },
    parameters: { capital_share: 0.3, savings_rate: 0.2 },
    policy: { new_savings_rate: o.newSavings ?? 0.3, policy_year: 10 },
    horizon_years: 100,
    baseline_steady_state: { capital: o.k0 ?? 2 },
    scenario_steady_state: { capital: o.k1 ?? 5 },
    golden_rule: { savings_rate: o.golden ?? 0.3 },
    convergence: { half_life_years: o.halfLife ?? 12 },
    scenario: { capital: [1, 2, o.finalK ?? 4] },
    metadata: meta("solow"),
  });
}

describe("summary diff: absolute and relative change", () => {
  it("works out current − reference and (current − reference)/|reference|", () => {
    // Hand-worked: 2 → 3 is +1 and +1/2 = +50%; -4 → -2 is +2 and +2/|-4| = +50%;
    // 5 → 4 is -1 and -1/5 = -20%; 4 → 4 is 0 and 0%.
    const rows = summaryDiff(
      solow({ k0: 2, k1: 5, halfLife: -4, finalK: 4 }),
      solow({ k0: 3, k1: 4, halfLife: -2, finalK: 4 }),
    );
    const by = Object.fromEntries(rows.map((r) => [r.field, r]));
    expect(by.baseline_steady_state_capital).toEqual({
      field: "baseline_steady_state_capital",
      kind: "number",
      reference: 2,
      current: 3,
      absolute: 1,
      relative: 0.5,
    });
    expect(by.scenario_steady_state_capital).toMatchObject({ absolute: -1, relative: -0.2 });
    expect(by.half_life_years).toMatchObject({ reference: -4, current: -2, absolute: 2 });
    expect(by.half_life_years).toMatchObject({ relative: 0.5 });
    expect(by.final_capital).toMatchObject({ absolute: 0, relative: 0 });
  });

  it("leaves the relative change undefined (null) when the reference is 0, never Infinity", () => {
    const [row] = summaryDiff(solow({ golden: 0 }), solow({ golden: 0.3 })).filter(
      (r) => r.field === "golden_rule_savings_rate",
    );
    expect(row).toEqual({
      field: "golden_rule_savings_rate",
      kind: "number",
      reference: 0,
      current: 0.3,
      absolute: 0.3,
      relative: null,
    });
    // 0 → 0 is no change at all, but the ratio 0/0 is still undefined.
    const [same] = summaryDiff(solow({ golden: 0 }), solow({ golden: 0 })).filter(
      (r) => r.field === "golden_rule_savings_rate",
    );
    expect(same).toMatchObject({ absolute: 0, relative: null });
  });

  it("lists the Solow summary fields the run record stores, in its order", () => {
    expect(summaryFields(solow({}))).toEqual({
      baseline_steady_state_capital: 2,
      scenario_steady_state_capital: 5,
      golden_rule_savings_rate: 0.3,
      half_life_years: 12,
      final_capital: 4,
    });
  });
});

describe("summary diff: values that are not numbers", () => {
  const profile = (o: { sampleId?: string | null; source?: string; rows?: number } = {}) =>
    as({
      ...PROFILE,
      dataset: { ...PROFILE.dataset, source: o.source ?? "sample", sample_id: o.sampleId ?? "x" },
      n_rows: o.rows ?? PROFILE.n_rows,
    });

  it("shows text, booleans and nulls as equal or changed, with no arithmetic", () => {
    const rows = summaryDiff(profile({ sampleId: "a" }), profile({ sampleId: "b" }));
    const by = Object.fromEntries(rows.map((r) => [r.field, r]));
    expect(by.source).toEqual({
      field: "source",
      kind: "other",
      reference: "sample",
      current: "sample",
      equal: true,
    });
    expect(by.sample_id).toEqual({
      field: "sample_id",
      kind: "other",
      reference: "a",
      current: "b",
      equal: false,
    });
  });

  it("treats null against a number as changed, not as zero", () => {
    const study = (order: number | null) =>
      as({
        model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study" },
        parameters: {},
        dt_values: [0.1],
        methods: ["euler"],
        horizon: 2,
        results: [
          {
            method: "euler",
            theoretical_order: 1,
            position_fit: order === null ? null : { order, n_points: 3 },
            velocity_fit: null,
            runs: [{ max_position_error: 0.5 }],
          },
        ],
        metadata: meta("s"),
      });
    const row = summaryDiff(study(null), study(1)).find(
      (r) => r.field === "methods.euler.position_order",
    );
    expect(row).toEqual({
      field: "methods.euler.position_order",
      kind: "other",
      reference: null,
      current: 1,
      equal: false,
    });
  });

  it("counts the dataset profile's summary by hand from the fixture", () => {
    // messy_survey: 10 rows, 6 columns, 7 missing cells, 1 duplicate row, and 2 mixed
    // columns (income_gbp: 6 numbers + 3 text; rating: 9 numbers + 1 text). The same counts
    // are derived by hand in backend/tests/quant/test_samples.py.
    expect(summaryFields(as(PROFILE))).toEqual({
      source: "sample",
      sample_id: "messy_survey",
      rows: 10,
      columns: 6,
      missing_cells: 7,
      duplicate_rows: 1,
      mixed_columns: 2,
    });
    const rows = summaryDiff(profile({ rows: 10 }), profile({ rows: 12 }));
    expect(rows.find((r) => r.field === "rows")).toMatchObject({ absolute: 2, relative: 0.2 });
  });

  it("marks a field present in only one run as changed", () => {
    const study = (methods: string[]) =>
      as({
        model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study" },
        parameters: {},
        dt_values: [0.1],
        methods,
        horizon: 2,
        results: methods.map((method) => ({
          method,
          theoretical_order: 1,
          position_fit: null,
          velocity_fit: null,
          runs: [{ max_position_error: null }],
        })),
        metadata: meta("s"),
      });
    const rows = summaryDiff(study(["euler"]), study(["euler", "rk4"]));
    expect(rows.find((r) => r.field === "methods.rk4.theoretical_order")).toEqual({
      field: "methods.rk4.theoretical_order",
      kind: "other",
      reference: undefined,
      current: 1,
      equal: false,
    });
  });
});

describe("the info note's condition: every number exactly equal", () => {
  it("is true only when every numeric change is exactly 0", () => {
    expect(allNumbersEqual(summaryDiff(solow({}), solow({})))).toBe(true);
    expect(allNumbersEqual(summaryDiff(solow({}), solow({ k0: 2.000000001 })))).toBe(false);
  });

  it("is false when there is no number to compare", () => {
    expect(allNumbersEqual([])).toBe(false);
  });

  it("is false when a value is a number in one run and missing or null in the other", () => {
    // Hand-built rows: the horizon is exactly equal, but the position order went from no fit
    // (null) to 1.2, so not every numeric value is equal.
    const rows = [
      { field: "horizon", kind: "number", reference: 2, current: 2, absolute: 0, relative: 0 },
      {
        field: "methods.euler.position_order",
        kind: "other",
        reference: null,
        current: 1.2,
        equal: false,
      },
    ] as const;
    expect(allNumbersEqual(rows)).toBe(false);
    // Text that changed is not a numeric value: the note may still be shown.
    const text = [
      rows[0],
      { field: "sample_id", kind: "other", reference: "a", current: "b", equal: false },
    ] as const;
    expect(allNumbersEqual(text)).toBe(true);
  });
});

describe("input diff", () => {
  it("lists only the inputs that differ, with both values", () => {
    expect(inputDiff(solow({ newSavings: 0.3 }), solow({ newSavings: 0.35 }))).toEqual([
      { field: "policy.new_savings_rate", reference: 0.3, current: 0.35 },
    ]);
    expect(inputDiff(solow({}), solow({}))).toEqual([]);
  });

  const parameters = { initial_speed: 20, launch_angle_deg: 45, mass: 1 };

  it("reads a projectile's inputs as stored, n_samples being the number of samples", () => {
    const r = as({
      model: { id: "physics.projectile", version: "1.0.0", name: "P" },
      parameters,
      solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
      series: { t: [0, 0.5, 1, 1.5, 2] },
      metadata: meta("p"),
    });
    expect(inputFields(r)).toEqual({
      "parameters.initial_speed": 20,
      "parameters.launch_angle_deg": 45,
      "parameters.mass": 1,
      "solver.method": "DOP853",
      "solver.rtol": 1e-10,
      "solver.atol": 1e-10,
      n_samples: 5,
    });
  });

  it("leaves the launch angle out of an angle sweep's inputs (a sweep does not use it)", () => {
    const sweep = (angle: number, n: number) =>
      as({
        model: { id: "physics.projectile.angle_sweep", version: "1.0.0", name: "S" },
        parameters: { ...parameters, launch_angle_deg: angle },
        angles_deg: Array.from({ length: n }, (_, i) => (90 * i) / (n - 1)),
        best_angle_deg: 40,
        best_range: 9,
        vacuum_best_angle_deg: 45,
        vacuum_best_range: 40,
        metadata: meta("s"),
      });
    expect(inputFields(sweep(30, 4))).toEqual({
      "parameters.initial_speed": 20,
      "parameters.mass": 1,
      n_angles: 4,
    });
    expect(inputDiff(sweep(30, 4), sweep(60, 4))).toEqual([]);
    expect(inputDiff(sweep(30, 4), sweep(30, 7))).toEqual([
      { field: "n_angles", reference: 4, current: 7 },
    ]);
  });

  it("quadratic angle sweep: parameters without the launch angle, the solver and n_angles", () => {
    // As the backend's QUADRATIC_ANGLE_SWEEP entry stores them (api/routes/physics.py).
    const sweep = (angle: number, n: number) =>
      as({
        model: { id: "physics.projectile.quadratic_angle_sweep", version: "1.0.0", name: "S" },
        parameters: { initial_speed: 20, launch_angle_deg: angle, drag_constant: 0.01 },
        solver: { method: "Radau", rtol: 1e-8, atol: 1e-9 },
        angles_deg: Array.from({ length: n }, (_, i) => (90 * i) / (n - 1)),
        metadata: meta("s"),
      });
    expect(inputFields(sweep(30, 11))).toEqual({
      "parameters.initial_speed": 20,
      "parameters.drag_constant": 0.01,
      "solver.method": "Radau",
      "solver.rtol": 1e-8,
      "solver.atol": 1e-9,
      n_angles: 11,
    });
    expect(inputDiff(sweep(30, 11), sweep(60, 11))).toEqual([]);
  });

  it("compares list inputs (step sizes, methods) as whole values", () => {
    const study = (dt: number[]) =>
      as({
        model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study" },
        parameters: { mass: 1 },
        dt_values: dt,
        methods: ["euler", "rk4"],
        horizon: 2,
        results: [],
        metadata: meta("s"),
      });
    expect(inputDiff(study([0.1, 0.05]), study([0.1, 0.05]))).toEqual([]);
    expect(inputDiff(study([0.1, 0.05]), study([0.1, 0.025]))).toEqual([
      { field: "dt_values", reference: [0.1, 0.05], current: [0.1, 0.025] },
    ]);
  });

  it("identifies a dataset profile's input by the file's hash and the parse options", () => {
    const changed = as({
      ...PROFILE,
      options: { ...PROFILE.options, delimiter: "semicolon" },
    });
    expect(inputDiff(as(PROFILE), changed)).toEqual([
      { field: "options.delimiter", reference: "comma", current: "semicolon" },
    ]);
    expect(Object.keys(inputFields(as(PROFILE)))).toEqual([
      "dataset.sha256",
      "dataset.byte_size",
      "options.delimiter",
      "options.missing_markers",
      "options.column_types",
    ]);
  });
});

describe("compareRuns", () => {
  it("compares only two runs of the same model", () => {
    expect(compareRuns(solow({}), as(PROFILE))).toBeNull();
    const c = compareRuns(solow({ newSavings: 0.3 }), solow({ newSavings: 0.4 }));
    expect(c?.inputs).toEqual([{ field: "policy.new_savings_rate", reference: 0.3, current: 0.4 }]);
    expect(c?.summary).toHaveLength(5);
  });
});

describe("summary fields of the physics models, as their run records store them", () => {
  it("projectile: analytical (without its note), numerical and comparison, flattened", () => {
    const metric = { absolute: 1e-12, relative: null };
    const r = as({
      model: { id: "physics.projectile", version: "1.0.0", name: "P" },
      analytical: { range: 20, flight_time: 2, method_note: "Exact." },
      numerical: { range: 20.5, method: "DOP853", n_steps: 7 },
      comparison: { range: metric, max_position_error: 2e-11 },
      metadata: meta("p"),
    });
    expect(summaryFields(r)).toEqual({
      "analytical.range": 20,
      "analytical.flight_time": 2,
      "numerical.range": 20.5,
      "numerical.method": "DOP853",
      "numerical.n_steps": 7,
      "comparison.range.absolute": 1e-12,
      "comparison.range.relative": null,
      "comparison.max_position_error": 2e-11,
    });
  });

  it("quadratic drag: numerical, terminal speed, vacuum (without its note), diagnostics", () => {
    // As _quadratic_summary in backend/src/simforge/api/routes/physics.py stores it: the
    // invariant's note and the vertical reference are shown, not stored.
    const r = as({
      model: { id: "physics.projectile.quadratic_drag", version: "1.0.0", name: "Q" },
      numerical: { range: 30.5, method: "DOP853", n_steps: 31 },
      numerical_note: "numerical: ...",
      terminal_speed: null,
      vacuum: { range: 40.79, flight_time: 2.88, method_note: "exact: ..." },
      vertical_reference: { exact: { flight_time: 4 } },
      diagnostics: {
        max_energy_balance_residual: 3e-13,
        max_invariant_residual: null,
        invariant_note: "Undefined.",
        drag_time_bound: 0.4,
        flight_time_bound: 7.5,
      },
      metadata: meta("q"),
    });
    expect(summaryFields(r)).toEqual({
      "numerical.range": 30.5,
      "numerical.method": "DOP853",
      "numerical.n_steps": 31,
      terminal_speed: null,
      "vacuum.range": 40.79,
      "vacuum.flight_time": 2.88,
      "diagnostics.max_energy_balance_residual": 3e-13,
      "diagnostics.max_invariant_residual": null,
      "diagnostics.drag_time_bound": 0.4,
      "diagnostics.flight_time_bound": 7.5,
    });
  });

  it("quadratic drag inputs: parameters, solver and n_samples (the number of samples)", () => {
    const r = as({
      model: { id: "physics.projectile.quadratic_drag", version: "1.0.0", name: "Q" },
      parameters: { initial_speed: 20, drag_constant: 0.01 },
      solver: { method: "RK45", rtol: 1e-8, atol: 1e-9 },
      series: { t: [0, 1, 2], vacuum_t: [0, 1, 2] },
      metadata: meta("q"),
    });
    expect(inputFields(r)).toEqual({
      "parameters.initial_speed": 20,
      "parameters.drag_constant": 0.01,
      "solver.method": "RK45",
      "solver.rtol": 1e-8,
      "solver.atol": 1e-9,
      n_samples: 3,
    });
  });

  it("quadratic angle sweep: the stored headline values, nulls kept in a vacuum", () => {
    const sweep = (u: number | null, vT: number | null) =>
      as({
        model: { id: "physics.projectile.quadratic_angle_sweep", version: "1.0.0", name: "S" },
        parameters: {},
        solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
        angles_deg: [0, 90],
        best_angle_deg: 42.98,
        best_range: 31.4,
        best_angle_uncertainty_deg: u,
        best_angle_note: "not stored",
        vacuum_best_angle_deg: 45,
        vacuum_best_range: 40.79,
        terminal_speed: vT,
        n_runs: 18,
        n_rhs_evaluations: 3024,
        metadata: meta("s"),
      });
    expect(summaryFields(sweep(0.002, 31.3))).toEqual({
      best_angle_deg: 42.98,
      best_range: 31.4,
      best_angle_uncertainty_deg: 0.002,
      vacuum_best_angle_deg: 45,
      vacuum_best_range: 40.79,
      terminal_speed: 31.3,
      n_rhs_evaluations: 3024,
    });
    const vacuum = summaryFields(sweep(null, null));
    expect(vacuum.best_angle_uncertainty_deg).toBeNull();
    expect(vacuum.terminal_speed).toBeNull();
  });

  it("angle sweep: the best angle and range, with and without drag", () => {
    const r = as({
      model: { id: "physics.projectile.angle_sweep", version: "1.0.0", name: "S" },
      parameters: {},
      angles_deg: [0, 90],
      best_angle_deg: 40,
      best_range: 9,
      vacuum_best_angle_deg: 45,
      vacuum_best_range: 40.79,
      metadata: meta("s"),
    });
    expect(summaryFields(r)).toEqual({
      best_angle_deg: 40,
      best_range: 9,
      vacuum_best_angle_deg: 45,
      vacuum_best_range: 40.79,
    });
  });

  it("integrator study: the horizon, then per method its orders and finest-step error", () => {
    const r = as({
      model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study" },
      horizon: 2,
      results: [
        {
          method: "euler",
          theoretical_order: 1,
          position_fit: { order: 0.98, n_points: 3 },
          velocity_fit: { order: 1.01, n_points: 3 },
          // The finest step is the last run.
          runs: [{ max_position_error: 0.4 }, { max_position_error: 0.2 }],
        },
        {
          method: "rk4",
          theoretical_order: 4,
          position_fit: null,
          velocity_fit: null,
          runs: [{ max_position_error: null }],
        },
      ],
      metadata: meta("s"),
    });
    expect(summaryFields(r)).toEqual({
      horizon: 2,
      "methods.euler.theoretical_order": 1,
      "methods.euler.position_order": 0.98,
      "methods.euler.position_fit_points": 3,
      "methods.euler.velocity_order": 1.01,
      "methods.euler.finest_max_position_error": 0.2,
      "methods.rk4.theoretical_order": 4,
      "methods.rk4.position_order": null,
      "methods.rk4.position_fit_points": 0,
      "methods.rk4.velocity_order": null,
      "methods.rk4.finest_max_position_error": null,
    });
  });
});
