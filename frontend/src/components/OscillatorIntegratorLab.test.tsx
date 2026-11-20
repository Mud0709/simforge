import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { OscillatorIntegratorResponse } from "@/lib/api/client";
import { OscillatorIntegratorLab } from "./OscillatorIntegratorLab";

/*
 * Contract for the builder (roadmap 2.4, plan D15). Red until implemented.
 *
 * Component: `OscillatorIntegratorLab` (named export of ./OscillatorIntegratorLab.tsx), no props,
 * rendered by the page /physics/oscillator/integrators (src/app/physics/oscillator/integrators/
 * page.tsx, h1 "Do symplectic integrators keep the energy?"), linked from /physics/oscillator
 * (link text "Compare integrators on the oscillator"). `OscillatorIntegratorResponse` must be
 * exported from "@/lib/api/client" (Schemas["OscillatorIntegratorResponse"]).
 *
 * Layout: the five workspace regions "Parameters", "Visualisation", "Results", "Assumptions",
 * "Validation" (as IntegratorLab), present before any run.
 * Parameters (labels start with, defaults from the OpenAPI schema): "Mass" 1 (kg), "Spring
 * constant" 25 (N/m), "Initial displacement" 0.1 (m), "Initial velocity" 0 (m/s), "Time steps"
 * (comma list, default the eight values 0.04/2^i, i = 0..7), "Energy time step" 0.05 (s),
 * "Periods" 200; one checkbox per method named /^Euler/, /^RK4/, /^Symplectic Euler/,
 * /^Velocity Verlet/ (all four checked by default); button "Run study" (POST
 * /api/v1/physics/oscillator/integrators with { parameters: {mass, spring_constant,
 * initial_displacement, initial_velocity}, dt_values, methods, energy_dt, periods }).
 * Client-side refusals (no API call): "Select at least one method", "Remove duplicate time steps".
 * A server 422 shows its detail in role="alert".
 * Results region: one row per method, data-testid `order-<method>` whose second cell is the fitted
 * order (as IntegratorLab), and a modified-energy table with one row `modified-energy-<method>`
 * per symplectic method (those whose modified_energy_residual is not null) showing the residual.
 * Visualisation region, two charts (PlotlyChart, `title` = aria-label):
 *   "Convergence: maximum scaled error against time step" (data: one trace per method, named by
 *   the method id, x = h of its runs with a non-null error, y = max_scaled_error), and
 *   "Energy drift: relative energy envelope against time" (data: one line trace per method named
 *   by the method id, built from that method's `energy[].envelope`).
 * Validation region: <ChecksTable checks={response.checks}/> (rows `check-<id>`) and the fit rule
 * text and run id. Assumptions region lists the response's assumptions.
 * Changing an input after a run shows "inputs have changed" in Results (as IntegratorLab).
 */

type Trace = { name?: string; x?: number[]; y?: number[] };
const charts = new Map<string, Trace[]>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, data }: { title: string; data: Trace[] }) => {
    charts.set(title, data);
    return <div role="img" aria-label={title} />;
  },
}));

const CONVERGENCE = "Convergence: maximum scaled error against time step";
const DRIFT = "Energy drift: relative energy envelope against time";

// Hand-made shape fixtures (not physics output): w = sqrt(25/1) = 5 rad/s, T = 2 pi / 5.
const run = (h: number, err: number | null) => ({
  dt_requested: h,
  h,
  n_steps: Math.round(1.2566 / h),
  n_completed: Math.round(1.2566 / h),
  theta: 5 * h,
  diverged: err === null,
  max_scaled_error: err,
  max_position_error: err,
  max_velocity_error: err,
  in_fit: err !== null,
  exclusion_reason: err === null ? "diverged" : null,
});
const fit = (order: number, theory: number) => ({
  order,
  theoretical_order: theory,
  r_squared: 0.9999,
  n_points: 3,
  h_min: 0.01,
  h_max: 0.04,
});
const result = (method: string, theory: number, fitted: number) => ({
  method,
  theoretical_order: theory,
  fit: fit(fitted, theory),
  runs: [run(0.04, 0.4), run(0.02, 0.2), run(0.01, 0.1)],
});
const energyRun = (method: string, residual: number | null) => ({
  method,
  h: 0.05,
  n_steps: 5000,
  n_completed: 5000,
  diverged: false,
  diverged_at_step: null,
  energy_bound: residual === null ? null : 0.01,
  final_energy_ratio: 1,
  max_relative_energy_error: 0.001,
  modified_energy_residual: residual,
  envelope: {
    t_start: [0, 100],
    t_end: [100, 200],
    lo: [0.99, 0.98],
    hi: [1.01, 1.02],
  },
});
const METHODS = ["euler", "rk4", "symplectic_euler", "velocity_verlet"] as const;
const RESPONSE = {
  model: { id: "physics.oscillator.integrators", version: "1.0.0", name: "Study", description: "" },
  parameters: { mass: 1, spring_constant: 25, initial_displacement: 0.1, initial_velocity: 0 },
  dt_values: [0.04, 0.02, 0.01],
  methods: [...METHODS],
  energy_dt: 0.05,
  periods: 200,
  period: 1.2566,
  angular_frequency: 5,
  amplitude_scale: 0.1,
  units: {},
  assumptions: [{ id: "undamped", statement: "Undamped, undriven oscillator." }],
  fit_rule: {
    max_theta: 0.5,
    max_amplitude_growth: 10,
    roundoff_safety_factor: 100,
    min_points: 3,
    description: "Fit rule text.",
  },
  results: [
    result("euler", 1, 1.02),
    result("rk4", 4, 3.98),
    result("symplectic_euler", 1, 1.01),
    result("velocity_verlet", 2, 2.0),
  ],
  energy: [
    energyRun("euler", null),
    energyRun("rk4", null),
    energyRun("symplectic_euler", 3.2e-15),
    energyRun("velocity_verlet", 4.1e-15),
  ],
  checks: [
    {
      id: "symplectic_energy_bound",
      label: "Symplectic energy bound",
      value: 0.001,
      threshold: 0.01,
      passed: true,
      kind: "exact_identity",
      note: "bound note",
    },
    {
      id: "cost",
      label: "Cost",
      value: 123,
      threshold: null,
      passed: null,
      kind: "informational",
      note: "cost note",
    },
  ],
  metadata: {
    run_id: "abc-123",
    created_at: "2026-01-01T00:00:00Z",
    input_hash: "f".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 80,
    experiment_saved: true,
  },
} as unknown as OscillatorIntegratorResponse;

function mockFetch(status: number, body: unknown) {
  const fn = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fn);
  return fn;
}

const region = (name: string) => screen.getByRole("region", { name });
async function runStudy() {
  await userEvent.click(screen.getByRole("button", { name: "Run study" }));
  await screen.findByTestId("order-rk4");
}

afterEach(() => {
  vi.unstubAllGlobals();
  charts.clear();
});

describe("OscillatorIntegratorLab", () => {
  it("lays out the five workspace sections with the backend's defaults before any run", () => {
    render(<OscillatorIntegratorLab />);
    for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
      expect(region(name)).toBeInTheDocument();
    }
    const params = within(region("Parameters"));
    const defaults: [RegExp, string][] = [
      [/^Mass/, "1"],
      [/^Spring constant/, "25"],
      [/^Initial displacement/, "0.1"],
      [/^Initial velocity/, "0"],
      [/^Energy time step/, "0.05"],
      [/^Periods/, "200"],
    ];
    for (const [label, value] of defaults) expect(params.getByLabelText(label)).toHaveValue(value);
    expect(params.getByLabelText(/^Time steps/)).toBeInTheDocument();
    for (const m of [/^Euler/, /^RK4/, /^Symplectic Euler/, /^Velocity Verlet/]) {
      expect(params.getByRole("checkbox", { name: m })).toBeChecked();
    }
  });

  it("sends the request to the integrators endpoint", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<OscillatorIntegratorLab />);
    await userEvent.click(screen.getByRole("checkbox", { name: /^Euler/ }));
    await runStudy();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/oscillator/integrators");
    const sent = JSON.parse(init.body);
    expect(sent.methods).toEqual(["rk4", "symplectic_euler", "velocity_verlet"]);
    expect(sent.parameters).toEqual({
      mass: 1,
      spring_constant: 25,
      initial_displacement: 0.1,
      initial_velocity: 0,
    });
    expect(sent.energy_dt).toBe(0.05);
    expect(sent.periods).toBe(200);
    // Defaults 0.04 / 2^i, i = 0..7: typed from the plan (D1/D2), not from the code.
    expect(sent.dt_values).toHaveLength(8);
    expect(sent.dt_values[0]).toBeCloseTo(0.04, 12);
    expect(sent.dt_values[7]).toBeCloseTo(0.04 / 128, 12);
  });

  it("puts orders, modified-energy rows, charts and checks in their sections", async () => {
    mockFetch(200, RESPONSE);
    render(<OscillatorIntegratorLab />);
    await runStudy();
    const results = within(region("Results"));
    expect(results.getByTestId("order-rk4")).toHaveTextContent("3.98");
    expect(results.getByTestId("order-velocity_verlet")).toHaveTextContent("2.00");
    // Only symplectic methods have a modified-energy residual (null elsewhere).
    expect(results.getByTestId("modified-energy-symplectic_euler")).toHaveTextContent("3.2e-15");
    expect(results.getByTestId("modified-energy-velocity_verlet")).toHaveTextContent("4.1e-15");
    expect(results.queryByTestId("modified-energy-euler")).not.toBeInTheDocument();
    expect(results.queryByTestId("modified-energy-rk4")).not.toBeInTheDocument();

    const vis = within(region("Visualisation"));
    expect(vis.getByRole("img", { name: CONVERGENCE })).toBeInTheDocument();
    expect(vis.getByRole("img", { name: DRIFT })).toBeInTheDocument();

    const validation = within(region("Validation"));
    expect(validation.getByTestId("check-symplectic_energy_bound")).toHaveTextContent("Pass");
    expect(validation.getByTestId("check-cost")).toHaveTextContent("Info");
    expect(validation.getByText(/Fit rule text\./)).toBeInTheDocument();
    expect(validation.getByText("abc-123")).toBeInTheDocument();
    expect(within(region("Assumptions")).getByText(/Undamped, undriven/)).toBeInTheDocument();
  });

  it("draws one convergence line and one energy-drift line per method", async () => {
    mockFetch(200, RESPONSE);
    render(<OscillatorIntegratorLab />);
    await runStudy();
    const conv = charts.get(CONVERGENCE)!;
    const drift = charts.get(DRIFT)!;
    for (const m of METHODS) {
      expect(conv.some((t) => t.name === m)).toBe(true);
      expect(drift.some((t) => t.name === m)).toBe(true);
    }
    const rk4 = conv.find((t) => t.name === "rk4")!;
    expect(rk4.x).toEqual([0.04, 0.02, 0.01]);
    expect(rk4.y).toEqual([0.4, 0.2, 0.1]);
  });

  it("refuses no methods and duplicate steps without calling the API", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<OscillatorIntegratorLab />);
    const steps = screen.getByLabelText(/^Time steps/);
    await userEvent.clear(steps);
    await userEvent.type(steps, "0.1, 0.1");
    for (const box of screen.getAllByRole("checkbox")) await userEvent.click(box);
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));
    expect(screen.getByText("Remove duplicate time steps")).toBeInTheDocument();
    expect(screen.getByText("Select at least one method")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("marks the study as out of date when an input changes", async () => {
    mockFetch(200, RESPONSE);
    render(<OscillatorIntegratorLab />);
    await runStudy();
    await userEvent.type(screen.getByLabelText(/^Periods/), "0");
    expect(within(region("Results")).getByText(/inputs have changed/)).toBeInTheDocument();
  });

  it("shows the server's explanation when a study is refused", async () => {
    mockFetch(422, { detail: "periods: Input should be less than or equal to 1000" });
    render(<OscillatorIntegratorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("less than or equal to 1000");
  });
});
