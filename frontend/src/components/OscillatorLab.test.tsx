import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { OscillatorResponse } from "@/lib/api/client";
import { OscillatorLab } from "./OscillatorLab";

// Plotly needs a real browser; the E2E test draws the charts. Here each chart's traces are
// recorded by title, so a test can read what would be drawn.
type Trace = {
  name?: string;
  x?: number[];
  y?: number[];
  mode?: string;
  line?: { dash?: string };
};
const charts = new Map<string, Trace[]>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, data }: { title: string; data: Trace[] }) => {
    charts.set(title, data);
    return <div role="img" aria-label={title} />;
  },
}));

const DISPLACEMENT = "Displacement against time";
const ENERGY = "Energy against time";
const RESONANCE = "Resonance: steady-state amplitude and phase against drive frequency";

// Small hand-made responses: only the shape matters here, not the physics. Every number is
// worked by hand from the inputs (w0 = sqrt(k/m), gamma = b/2m, zeta = b/(2 sqrt(mk)),
// Q = sqrt(mk)/b, wd = sqrt(w0^2 - gamma^2), T_d = 2 pi/wd, A = (F0/m)/(2 gamma w) at w = w0),
// none is produced by the code under test.
const check = (id: string, label: string, value: number, threshold: number | null) => ({
  id,
  label,
  value,
  threshold,
  passed: threshold === null ? null : value <= threshold,
  kind: threshold === null ? "informational" : "numerical_diagnostic",
  note: `${label} note`,
});
const UNITS = { t: "s", x: "m", v: "m/s", energy: "J" };
const SOLVER = { method: "DOP853", rtol: 1e-10, atol: 1e-10 };
const PARAMS = {
  mass: 1,
  spring_constant: 25,
  damping_coefficient: 0.5,
  drive_amplitude: 0,
  drive_angular_frequency: 5,
  initial_displacement: 0.1,
  initial_velocity: 0,
  duration: 20,
};
const series = (envelope: number[] | null) => ({
  t: [0, 10, 20],
  x: [0.1, -0.05, 0.02],
  v: [0, 0.3, -0.2],
  x_exact: [0.1, -0.05, 0.02],
  v_exact: [0, 0.3, -0.2],
  envelope,
  kinetic_energy: [0, 0.045, 0.02],
  potential_energy: [0.125, 0.03125, 0.005],
  damping_work: [0, 0.05, 0.1],
  drive_work: [0, 0, 0],
});
const BASE = {
  model: {
    id: "physics.oscillator",
    version: "1.0.0",
    name: "Harmonic oscillator (simple, damped, driven)",
    description: "",
  },
  parameters: PARAMS,
  solver: SOLVER,
  units: UNITS,
  assumptions: [{ id: "linear_damping", statement: "Damping is linear, F = -b v." }],
  derived: {
    natural_angular_frequency: 5,
    damping_rate: 0.25,
    damping_ratio: 0.05,
    quality_factor: 10,
    regime: "underdamped",
    damped_angular_frequency: 4.99375,
    overdamped_rate: null,
    damped_period: 1.2582,
    scale: 0.1,
  },
  steady_state: null,
  numerical: {
    final_displacement: 0.02,
    final_velocity: -0.2,
    n_steps: 120,
    n_rhs_evaluations: 1600,
    method: "DOP853",
    rtol: 1e-10,
    atol: 1e-10,
  },
  diagnostics: {
    max_displacement_error: 2e-11,
    max_velocity_error: 3e-11,
    max_energy_balance_residual: 4e-12,
    free_decay_period_residual: 5e-12,
    free_decay_ratio_residual: 6e-12,
    remaining_transient: null,
    cycles: 3.18,
    stiffness_number: 100,
  },
  checks: [
    check("displacement_error", "Displacement vs the exact solution", 2e-11, 1e-6),
    check("energy_balance", "Energy balance KE + PE + W_damp - W_drive = E0", 4e-12, 1e-6),
    check("cost", "Solver cost", 1600, null),
  ],
  series: series([0.1, 0.0082, 0.00067]),
  resonance: null,
  method_note: "numerical: adaptive Runge-Kutta solve of the scaled equation",
  metadata: {
    run_id: "osc-run-1",
    created_at: "2026-01-01T00:00:00Z",
    input_hash: "e".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 3,
    experiment_saved: true,
  },
};
/** Damped, undriven: the page's default run (D12: steady_state and resonance are null). */
const DAMPED = BASE as unknown as OscillatorResponse;

/** Driven at w0 with b = 0.5, F0 = 2: A = 2/(2 x 0.25 x 5) = 0.8 m, delta = pi/2. */
const DRIVEN = {
  ...BASE,
  parameters: { ...PARAMS, drive_amplitude: 2 },
  steady_state: {
    amplitude: 0.8,
    phase_lag: 1.5708,
    peak_angular_frequency: 4.98749,
    peak_amplitude: 0.801,
  },
  diagnostics: { ...BASE.diagnostics, remaining_transient: 0.0123 },
  series: { ...series([0.1, 0.0082, 0.00067]), drive_work: [0, 0.4, 0.9] },
  resonance: {
    angular_frequency: [0, 5, 15],
    amplitude: [0.0032, 0.8, 0.0042],
    phase_lag: [0, 1.5708, 3.1],
  },
  checks: [...BASE.checks, check("steady_state_reached", "Steady state reached", 0.0123, null)],
  metadata: { ...BASE.metadata, run_id: "osc-run-2" },
} as unknown as OscillatorResponse;

/** Simple harmonic motion: b = 0, F0 = 0. Q, the envelope and the steady state do not exist. */
const SIMPLE = {
  ...BASE,
  parameters: { ...PARAMS, damping_coefficient: 0 },
  derived: {
    ...BASE.derived,
    damping_rate: 0,
    damping_ratio: 0,
    quality_factor: null,
    regime: "undamped",
    damped_angular_frequency: 5,
    damped_period: 1.2566,
  },
  diagnostics: { ...BASE.diagnostics, remaining_transient: null },
  series: series(null),
  metadata: { ...BASE.metadata, run_id: "osc-run-3" },
} as unknown as OscillatorResponse;

/** b = 12 (m = 1, k = 25): gamma = 6, zeta = 1.2, Q = 5/12, beta = sqrt(36 - 25) = 3.3166. */
const OVERDAMPED = {
  ...BASE,
  parameters: { ...PARAMS, damping_coefficient: 12 },
  solver: { method: "Radau", rtol: 1e-10, atol: 1e-10 },
  derived: {
    natural_angular_frequency: 5,
    damping_rate: 6,
    damping_ratio: 1.2,
    quality_factor: 0.41667,
    regime: "overdamped",
    damped_angular_frequency: null,
    overdamped_rate: 3.3166,
    damped_period: null,
    scale: 0.1,
  },
  diagnostics: {
    ...BASE.diagnostics,
    free_decay_period_residual: null,
    free_decay_ratio_residual: null,
  },
  series: series(null),
  metadata: { ...BASE.metadata, run_id: "osc-run-4" },
} as unknown as OscillatorResponse;

function mockFetch(status: number, body: unknown) {
  const fetchMock = vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  );
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const region = (name: string) => within(screen.getByRole("region", { name }));

async function run(body: unknown = DAMPED) {
  const fetchMock = mockFetch(200, body);
  await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
  await screen.findByText(/Run complete/);
  return fetchMock;
}

/** The value shown beside a Results label (the label is a <dt>, its value the next <dd>). */
const valueOf = (label: string) => region("Results").getByText(label).nextSibling;

afterEach(() => {
  vi.unstubAllGlobals();
  charts.clear();
});

const field = (label: RegExp) => screen.getByLabelText(label);

describe("OscillatorLab: the form and the presets", () => {
  it("builds its fields from the OpenAPI schema, with units and the backend's defaults", () => {
    render(<OscillatorLab />);
    const params = region("Parameters");
    // Defaults typed from OscillatorParameters in
    // backend/src/simforge/physics/oscillator/schemas.py:45-70 and SolverSettings.
    const expected: [RegExp, string, string][] = [
      [/^Mass/, "kg", "1"],
      [/^Spring constant/, "N/m", "25"],
      [/^Damping coefficient/, "kg/s", "0.5"],
      [/^Drive amplitude/, "N", "0"],
      [/^Drive angular frequency/, "rad/s", "5"],
      [/^Initial displacement/, "m", "0.1"],
      [/^Initial velocity/, "m/s", "0"],
      [/^Duration/, "s", "20"],
      [/^Relative tolerance/, "", "1e-10"],
      [/^Absolute tolerance/, "", "1e-10"],
    ];
    for (const [label, unit, value] of expected) {
      const input = params.getByLabelText(label);
      expect(input).toHaveValue(value);
      const labelEl = document.querySelector(`label[for="${input.id}"]`);
      if (unit) expect(labelEl).toHaveTextContent(`(${unit})`);
      else expect(labelEl).not.toHaveTextContent("(");
    }
    expect(params.getByLabelText("Method")).toHaveValue("DOP853");
  });

  it("has three preset buttons above the form: Simple, Damped and Driven", () => {
    render(<OscillatorLab />);
    for (const name of ["Simple", "Damped", "Driven"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("Simple fills the form with no damping and no drive (b = 0, F0 = 0)", async () => {
    render(<OscillatorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(field(/^Damping coefficient/)).toHaveValue("0");
    expect(field(/^Drive amplitude/)).toHaveValue("0");
    // Something must move (the backend refuses x0 = v0 = F0 = 0).
    const x0 = Number((field(/^Initial displacement/) as HTMLInputElement).value);
    const v0 = Number((field(/^Initial velocity/) as HTMLInputElement).value);
    expect(x0 !== 0 || v0 !== 0).toBe(true);
  });

  it("Damped fills the form with the contract's defaults: light damping, undriven", async () => {
    render(<OscillatorLab />);
    // Change things first, so the preset has something to put back.
    await userEvent.click(screen.getByRole("button", { name: "Driven" }));
    await userEvent.click(screen.getByRole("button", { name: "Damped" }));
    // D2: m = 1, k = 25, b = 0.5 (zeta = 0.05), F0 = 0, x0 = 0.1, v0 = 0, duration 20.
    expect(field(/^Mass/)).toHaveValue("1");
    expect(field(/^Spring constant/)).toHaveValue("25");
    expect(field(/^Damping coefficient/)).toHaveValue("0.5");
    expect(field(/^Drive amplitude/)).toHaveValue("0");
    expect(field(/^Initial displacement/)).toHaveValue("0.1");
    expect(field(/^Initial velocity/)).toHaveValue("0");
    expect(field(/^Duration/)).toHaveValue("20");
  });

  it("Driven fills the form with damping and a drive at the natural frequency", async () => {
    render(<OscillatorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Driven" }));
    const num = (label: RegExp) => Number((field(label) as HTMLInputElement).value);
    expect(num(/^Damping coefficient/)).toBeGreaterThan(0);
    expect(num(/^Drive amplitude/)).toBeGreaterThan(0);
    // w = w0 = sqrt(k/m), to the digits typed in the field (the exact formula).
    const w0 = Math.sqrt(num(/^Spring constant/) / num(/^Mass/));
    expect(num(/^Drive angular frequency/)).toBeCloseTo(w0, 6);
  });

  it("a preset only fills fields: nothing is sent until Run simulation", async () => {
    const fetchMock = mockFetch(200, DAMPED);
    render(<OscillatorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Simple" }));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("blocks invalid input without calling the API", async () => {
    const fetchMock = mockFetch(200, DAMPED);
    render(<OscillatorLab />);
    const k = field(/^Spring constant/);
    await userEvent.clear(k);
    await userEvent.type(k, "0");
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(screen.getByText("Must be ≥ 0.000001")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("OscillatorLab: running and the results", () => {
  it("sends the form to the oscillator endpoint", async () => {
    render(<OscillatorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Driven" }));
    const fetchMock = await run(DRIVEN);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/oscillator/simulate");
    const sent = JSON.parse(init.body);
    expect(Object.keys(sent.parameters).sort()).toEqual(Object.keys(PARAMS).sort());
    expect(sent.parameters.drive_amplitude).toBeGreaterThan(0);
    expect(sent.solver).toEqual(SOLVER);
  });

  it("labels every number in Results as numerical, exact or formula", async () => {
    render(<OscillatorLab />);
    await run(DRIVEN);
    const labels = [...screen.getByRole("region", { name: "Results" }).querySelectorAll("dt")].map(
      (dt) => dt.textContent ?? "",
    );
    expect(labels.length).toBeGreaterThanOrEqual(8);
    for (const l of labels) expect(l).toMatch(/\((numerical|exact|formula)\)$/);
  });

  it("shows the derived quantities with units, labelled by how they were obtained", async () => {
    render(<OscillatorLab />);
    await run(DAMPED);
    const results = region("Results");
    expect(valueOf("Natural angular frequency ω₀ (formula)")).toHaveTextContent("5 rad/s");
    expect(valueOf("Damping rate γ (formula)")).toHaveTextContent("0.25 1/s");
    expect(valueOf("Damping ratio ζ (formula)")).toHaveTextContent("0.05");
    expect(valueOf("Quality factor Q (formula)")).toHaveTextContent("10");
    expect(valueOf("Regime (exact)")).toHaveTextContent(/underdamped/i);
    expect(valueOf("Damped angular frequency ω_d (formula)")).toHaveTextContent("4.99375 rad/s");
    expect(valueOf("Damped period T_d (formula)")).toHaveTextContent("1.2582 s");
    expect(valueOf("Final displacement (numerical)")).toHaveTextContent("0.02 m");
    expect(valueOf("Final velocity (numerical)")).toHaveTextContent("-0.2 m/s");
    expect(results.getByText(/adaptive Runge-Kutta solve/)).toHaveTextContent(
      "DOP853, rtol = 1e-10, atol = 1e-10",
    );
    expect(results.getByRole("button", { name: "Download time series (CSV)" })).toBeInTheDocument();
    expect(region("Assumptions").getByText("Damping is linear, F = -b v.")).toBeInTheDocument();
    expect(region("Validation").getByText("osc-run-1")).toBeInTheDocument();
  });

  it("shows the steady state of a driven run: amplitude, phase lag, peak", async () => {
    render(<OscillatorLab />);
    await run(DRIVEN);
    expect(valueOf("Steady-state amplitude A (formula)")).toHaveTextContent("0.8 m");
    expect(valueOf("Phase lag δ (formula)")).toHaveTextContent("1.5708 rad");
    expect(valueOf("Amplitude peak at ω_r (formula)")).toHaveTextContent("4.98749 rad/s");
    expect(valueOf("Peak amplitude A_max (formula)")).toHaveTextContent("0.801 m");
  });

  it("shows D12's nulls as absent, never as 0: undriven (no steady state)", async () => {
    render(<OscillatorLab />);
    await run(DAMPED);
    for (const label of [
      "Steady-state amplitude A (formula)",
      "Phase lag δ (formula)",
      "Amplitude peak at ω_r (formula)",
      "Peak amplitude A_max (formula)",
    ]) {
      const v = valueOf(label);
      expect(v).toHaveTextContent(/^none/);
      expect(v).not.toHaveTextContent(/\d/); // no number at all, in particular no "0 m"
    }
  });

  it("shows D12's nulls as absent, never as 0: no damping (b = 0) has no Q and no steady state", async () => {
    render(<OscillatorLab />);
    await run(SIMPLE);
    expect(valueOf("Quality factor Q (formula)")).toHaveTextContent(/^none/);
    expect(valueOf("Quality factor Q (formula)")).not.toHaveTextContent(/\d/);
    // Undamped: wd = w0 and the period are present, as the backend sends them.
    expect(valueOf("Damped period T_d (formula)")).toHaveTextContent("1.2566 s");
    expect(valueOf("Steady-state amplitude A (formula)")).toHaveTextContent(/^none/);
    expect(valueOf("Regime (exact)")).toHaveTextContent(/undamped/i);
  });

  it("shows D12's nulls as absent, never as 0: overdamped has beta but no wd and no period", async () => {
    render(<OscillatorLab />);
    await run(OVERDAMPED);
    expect(valueOf("Regime (exact)")).toHaveTextContent(/overdamped/i);
    expect(valueOf("Overdamped rate β (formula)")).toHaveTextContent("3.3166 1/s");
    for (const label of ["Damped angular frequency ω_d (formula)", "Damped period T_d (formula)"]) {
      expect(valueOf(label)).toHaveTextContent(/^none/);
      expect(valueOf(label)).not.toHaveTextContent(/\d/);
    }
    expect(valueOf("Quality factor Q (formula)")).toHaveTextContent("0.41667");
  });

  it("shows the checks with their labels under Validation", async () => {
    render(<OscillatorLab />);
    await run(DAMPED);
    const validation = region("Validation");
    const energy = validation.getByTestId("check-energy_balance");
    expect(energy).toHaveTextContent("Energy balance KE + PE + W_damp - W_drive = E0");
    expect(energy).toHaveTextContent("Pass");
    expect(validation.getByTestId("check-cost")).toHaveTextContent("Info");
    expect(validation.getByTestId("check-displacement_error")).toHaveTextContent("Pass");
  });

  it("marks the results as out of date when an input changes, until the next run", async () => {
    render(<OscillatorLab />);
    await run();
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
    const b = field(/^Damping coefficient/);
    await userEvent.type(b, "5");
    expect(region("Validation").getByText(/inputs have changed/)).toBeInTheDocument();
    await userEvent.type(b, "{backspace}");
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
  });

  it("shows the server's reason when it refuses a run (422)", async () => {
    // FastAPI's 422 body for a combined rule: loc is ["body", "parameters"].
    mockFetch(422, {
      detail: [
        {
          loc: ["body", "parameters"],
          msg:
            "Value error, the drive frequency w = 700 rad/s is above 100 w0 = 500 rad/s; " +
            "lower drive_angular_frequency",
        },
      ],
    });
    render(<OscillatorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/the drive frequency w = 700 rad\/s is above 100 w0/);
    expect(alert).toHaveTextContent("lower drive_angular_frequency");
    expect(alert).not.toHaveTextContent("Value error");
    expect(region("Results").queryByText("Final displacement (numerical)")).not.toBeInTheDocument();
  });
});

describe("OscillatorLab: the charts", () => {
  it("draws displacement (numerical solid, exact dashed, envelope dotted) and the energy", async () => {
    render(<OscillatorLab />);
    await run(DAMPED);
    const vis = region("Visualisation");
    for (const name of [DISPLACEMENT, ENERGY]) {
      expect(vis.getByRole("img", { name })).toBeInTheDocument();
    }
    const disp = charts.get(DISPLACEMENT)!;
    expect(disp[0]!.name).toBe("Displacement (numerical, DOP853)");
    expect(disp[0]!.x).toEqual([0, 10, 20]);
    expect(disp[0]!.y).toEqual([0.1, -0.05, 0.02]);
    expect(disp[1]!.name).toBe("Exact (formula)");
    expect(disp[1]!.line?.dash).toBe("dash");
    // The envelope +-R e^(-gamma t), dotted, only when underdamped: +e and -e.
    const env = disp.filter((t) => t.name?.startsWith("Envelope"));
    expect(env).toHaveLength(2);
    expect(env.map((t) => t.line?.dash)).toEqual(["dot", "dot"]);
    expect(env[0]!.y).toEqual([0.1, 0.0082, 0.00067]);
    expect(env[1]!.y).toEqual([-0.1, -0.0082, -0.00067]);

    const energy = charts.get(ENERGY)!;
    const byName = (n: RegExp) => energy.find((t) => n.test(t.name ?? ""));
    expect(byName(/^Kinetic/)!.y).toEqual([0, 0.045, 0.02]);
    expect(byName(/^Potential/)!.y).toEqual([0.125, 0.03125, 0.005]);
    expect(byName(/damping/i)!.y).toEqual([0, 0.05, 0.1]);
    expect(byName(/drive/i)!.y).toEqual([0, 0, 0]);
  });

  it("draws no envelope when undamped or overdamped (the backend sends null)", async () => {
    const first = render(<OscillatorLab />);
    await run(SIMPLE);
    expect(charts.get(DISPLACEMENT)!.map((t) => t.name)).toEqual([
      "Displacement (numerical, DOP853)",
      "Exact (formula)",
    ]);
    first.unmount();
    render(<OscillatorLab />);
    await run(OVERDAMPED);
    expect(charts.get(DISPLACEMENT)!.map((t) => t.name)).toEqual([
      "Displacement (numerical, Radau)",
      "Exact (formula)",
    ]);
  });

  it("draws the resonance curve only when F0 > 0, with this run marked", async () => {
    const first = render(<OscillatorLab />);
    await run(DAMPED);
    expect(region("Visualisation").queryByRole("img", { name: RESONANCE })).not.toBeInTheDocument();
    expect(charts.has(RESONANCE)).toBe(false);
    first.unmount();

    render(<OscillatorLab />);
    await run(DRIVEN);
    expect(region("Visualisation").getByRole("img", { name: RESONANCE })).toBeInTheDocument();
    const res = charts.get(RESONANCE)!;
    expect(res.map((t) => t.name)).toEqual([
      "Amplitude (formula)",
      "Phase lag (formula)",
      "This run",
    ]);
    expect(res[0]!.x).toEqual([0, 5, 15]);
    expect(res[0]!.y).toEqual([0.0032, 0.8, 0.0042]);
    expect(res[1]!.y).toEqual([0, 1.5708, 3.1]);
    // This run: the drive frequency (5 rad/s) and its steady-state amplitude (0.8 m).
    expect(res[2]!.x).toEqual([5]);
    expect(res[2]!.y).toEqual([0.8]);
  });

  it("explains the missing resonance curve instead of drawing an empty chart", async () => {
    render(<OscillatorLab />);
    await run(SIMPLE);
    expect(region("Visualisation").getByText(/resonance curve .*drive/i)).toBeInTheDocument();
  });
});
