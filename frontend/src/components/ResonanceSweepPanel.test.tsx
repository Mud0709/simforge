/**
 * The simulated resonance curve panel (roadmap 2.5, slice 5, plan D13), on /physics/oscillator.
 *
 * Contract assumed here (the builder follows it; see the slice report):
 *  - `ResonanceSweepPanel` is exported from "./ResonanceSweepPanel", takes no required props,
 *    has its own form (it does not read the simulation form beside it) and its own run button.
 *  - Its section is a region named "Simulated resonance curve".
 *  - Field labels start with: "Sweep mass", "Sweep spring constant", "Sweep damping coefficient",
 *    "Sweep drive amplitude", "Lowest drive frequency", "Highest drive frequency",
 *    "Number of frequencies", "Settle tolerance", "Sweep relative tolerance",
 *    "Sweep absolute tolerance", and a select "Sweep solver method" (DOP853 and RK45 only: the
 *    server refuses Radau). None starts like the simulation form's labels, so both forms can
 *    share one page.
 *  - Button "Sweep drive frequency" (busy: "Sweeping…"); POST to
 *    /api/v1/physics/oscillator/resonance-sweep with { parameters, solver, n_frequencies }.
 *
 * Every response below is hand-made; each number is worked on paper from the defaults
 * (m = 1 kg, k = 25 N/m, b = 1 kg/s, F0 = 1 N): w0 = sqrt(k/m) = 5 rad/s, gamma = b/2m = 0.5 1/s,
 * A(w) = (F0/m) / sqrt((w0^2 - w^2)^2 + (2 gamma w)^2), delta(w) = atan2(2 gamma w, w0^2 - w^2),
 * w_r = sqrt(w0^2 - 2 gamma^2) = sqrt(24.5) = 4.94975 rad/s,
 * A_max = (F0/m) / (2 gamma sqrt(w0^2 - gamma^2)) = 1/sqrt(24.75) = 0.201008 m.
 * None is produced by the code under test.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { components } from "@/lib/api/schema";
import { ResonanceSweepPanel } from "./ResonanceSweepPanel";

type ResonanceSweepResponse = components["schemas"]["ResonanceSweepResponse"];

// Plotly needs a real browser (the E2E test draws it). Each chart's traces and layout are
// recorded by title, so a test can read what would be drawn.
type Trace = {
  name?: string;
  x?: number[];
  y?: number[];
  mode?: string;
  line?: { dash?: string };
};
type Layout = { xaxis?: { title?: { text?: string } }; yaxis?: { title?: { text?: string } } };
const charts = new Map<string, { data: Trace[]; layout: Layout }>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, data, layout }: { title: string; data: Trace[]; layout: Layout }) => {
    charts.set(title, { data, layout });
    return <div role="img" aria-label={title} />;
  },
}));

const CHART = "Simulated resonance curve: amplitude against drive frequency";

const check = (
  id: string,
  label: string,
  value: number,
  threshold: number | null,
  kind = threshold === null ? "informational" : "numerical_diagnostic",
) => ({
  id,
  label,
  value,
  threshold,
  passed: threshold === null ? null : value <= threshold,
  kind,
  note: `${label} note`,
});

const BASE = {
  model: {
    id: "physics.oscillator.resonance_sweep",
    version: "1.0.0",
    name: "Simulated resonance curve (driven, damped oscillator)",
    description: "",
  },
  parameters: {
    mass: 1,
    spring_constant: 25,
    damping_coefficient: 1,
    drive_amplitude: 1,
    omega_min: 0.5,
    omega_max: 15,
    settle_tolerance: 1e-6,
  },
  solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
  units: { angular_frequency: "rad/s", amplitude: "m", phase_lag: "rad" },
  assumptions: [{ id: "starts_from_rest", statement: "Every run starts from rest." }],
  // Three grid points: A(0.5) = 1/sqrt(24.75^2 + 0.5^2) = 0.040396,
  // A(5) = 1/sqrt(0 + 5^2) = 0.2, A(15) = 1/sqrt(200^2 + 15^2) = 0.0049860.
  angular_frequencies: [0.5, 5, 15],
  amplitudes: [0.040396, 0.2, 0.004986],
  exact_amplitudes: [0.040396, 0.2, 0.004986],
  // delta = atan2(w, 25 - w^2): 0.5/24.75 -> 0.020201; pi/2 = 1.570796; pi - atan(15/200) = 3.066743.
  phase_lags: [0.020201, 1.570796, 3.066743],
  exact_phase_lags: [0.020201, 1.570796, 3.066743],
  settle_times: [12.566, 25.133, 37.699],
  amplitude_bounds: [1e-7, 1e-7, 1e-7],
  // The exact curve on a fine grid: A(0) = F0/k = 1/25 = 0.04, A(5) = 0.2, A(15) = 0.0049860.
  resonance: {
    angular_frequency: [0, 5, 15],
    amplitude: [0.04, 0.2, 0.004986],
    phase_lag: [0, 1.570796, 3.066743],
  },
  // Grid step (15 - 0.5)/(3 - 1) = 7.25 rad/s over gamma = 0.5 1/s.
  grid_step_over_gamma: 14.5,
  n_rhs_evaluations: 4321,
  peak: {
    angular_frequency: 4.9497,
    amplitude: 0.201,
    amplitude_bound: 2e-7,
    uncertainty: 0.0016,
    uncertainty_note: "Estimate, not a bound: u = 2 sqrt(B1/K), from the grid's second difference.",
    exact_angular_frequency: 4.949747,
    exact_amplitude: 0.2010076,
  },
  checks: [
    check("lock_in_amplitude", "Lock-in amplitude vs the exact A(w)", 3e-9, 1e-7),
    check("peak_frequency", "Refined peak vs the exact w_r", 1.5e-6, 1.6e-3),
    check("cost", "Solver cost", 4321, null),
  ],
  metadata: {
    run_id: "res-run-1",
    created_at: "2026-01-01T00:00:00Z",
    input_hash: "c".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 2400,
    experiment_saved: true,
  },
};
const RESPONSE = BASE as unknown as ResonanceSweepResponse;

/** zeta >= 1/sqrt(2) (b = 8 with m = 1, k = 25: zeta = 0.8): no interior peak, so no w_r, no
 *  A_max and no u; the best grid point is the lowest frequency, an edge. */
const NO_PEAK = {
  ...BASE,
  parameters: { ...BASE.parameters, damping_coefficient: 8 },
  peak: {
    angular_frequency: 0.5,
    amplitude: 0.0399,
    amplitude_bound: 4e-8,
    uncertainty: null,
    uncertainty_note: "No estimate: the best grid point is at an edge of the grid.",
    exact_angular_frequency: null,
    exact_amplitude: null,
  },
  metadata: { ...BASE.metadata, run_id: "res-run-2" },
} as unknown as ResonanceSweepResponse;

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

afterEach(() => {
  vi.unstubAllGlobals();
  charts.clear();
});

const panel = () => within(screen.getByRole("region", { name: "Simulated resonance curve" }));
const sweepButton = () => screen.getByRole("button", { name: "Sweep drive frequency" });

async function sweep(body: unknown = RESPONSE) {
  const fetchMock = mockFetch(200, body);
  render(<ResonanceSweepPanel />);
  await userEvent.click(sweepButton());
  await screen.findByTestId("peak-frequency");
  return fetchMock;
}

describe("ResonanceSweepPanel: the form", () => {
  it("has fields with units and the contract's defaults (plan D11: w0 = 5, zeta = 0.1)", () => {
    render(<ResonanceSweepPanel />);
    // Defaults typed from ResonanceSweepParameters and SolverSettings in the OpenAPI contract.
    const expected: [RegExp, string, string][] = [
      [/^Sweep mass/, "kg", "1"],
      [/^Sweep spring constant/, "N/m", "25"],
      [/^Sweep damping coefficient/, "kg/s", "1"],
      [/^Sweep drive amplitude/, "N", "1"],
      [/^Lowest drive frequency/, "rad/s", "0.5"],
      [/^Highest drive frequency/, "rad/s", "15"],
      [/^Number of frequencies/, "", "21"],
      [/^Settle tolerance/, "", "0.000001"],
      [/^Sweep relative tolerance/, "", "1e-10"],
      [/^Sweep absolute tolerance/, "", "1e-10"],
    ];
    for (const [label, unit, value] of expected) {
      const input = panel().getByLabelText(label);
      expect(input).toHaveValue(value);
      const labelEl = document.querySelector(`label[for="${input.id}"]`);
      if (unit) expect(labelEl).toHaveTextContent(`(${unit})`);
      else expect(labelEl).not.toHaveTextContent("(");
    }
    expect(panel().getByLabelText("Sweep solver method")).toHaveValue("DOP853");
  });

  it("offers DOP853 and RK45 only: the server refuses Radau for an underdamped run", () => {
    render(<ResonanceSweepPanel />);
    const options = within(panel().getByLabelText("Sweep solver method")).getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual(["DOP853", "RK45"]);
  });

  it("sends nothing until the button is pressed", () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<ResonanceSweepPanel />);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(sweepButton()).toBeEnabled();
  });

  it("blocks an invalid number of frequencies without calling the API", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<ResonanceSweepPanel />);
    const n = panel().getByLabelText(/^Number of frequencies/);
    await userEvent.clear(n);
    await userEvent.type(n, "2"); // the contract's minimum is 3
    await userEvent.click(sweepButton());
    expect(panel().getByText("Must be ≥ 3")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });
});

describe("ResonanceSweepPanel: running the default", () => {
  it("posts the default parameters, solver and 21 frequencies to the resonance-sweep endpoint", async () => {
    const fetchMock = await sweep();
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/oscillator/resonance-sweep");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body)).toEqual({
      parameters: BASE.parameters,
      solver: BASE.solver,
      n_frequencies: 21,
    });
  });

  it("sends what was typed", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<ResonanceSweepPanel />);
    const type = async (label: RegExp, value: string) => {
      const input = panel().getByLabelText(label);
      await userEvent.clear(input);
      await userEvent.type(input, value);
    };
    await type(/^Sweep mass/, "1.3");
    await type(/^Sweep damping coefficient/, "0.9");
    await type(/^Lowest drive frequency/, "3");
    await type(/^Highest drive frequency/, "7");
    await type(/^Number of frequencies/, "15");
    await userEvent.selectOptions(panel().getByLabelText("Sweep solver method"), "RK45");
    await userEvent.click(sweepButton());
    await screen.findByTestId("peak-frequency");
    const sent = JSON.parse(fetchMock.mock.calls[0]![1].body);
    expect(sent.parameters).toEqual({
      ...BASE.parameters,
      mass: 1.3,
      damping_coefficient: 0.9,
      omega_min: 3,
      omega_max: 7,
    });
    expect(sent.solver.method).toBe("RK45");
    expect(sent.n_frequencies).toBe(15);
  });

  it("shows 'Sweeping…' and disables the button while the server works", async () => {
    let finish!: (r: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
    );
    render(<ResonanceSweepPanel />);
    await userEvent.click(sweepButton());
    const busy = await screen.findByRole("button", { name: "Sweeping…" });
    expect(busy).toBeDisabled();
    finish(
      new Response(JSON.stringify(RESPONSE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(await screen.findByTestId("peak-frequency")).toBeInTheDocument();
  });

  it("shows the server's explanation when it refuses (422), and no result", async () => {
    mockFetch(422, {
      detail: [
        {
          loc: ["body", "parameters"],
          msg: "Value error, omega_min (9 rad/s) must be below omega_max (4 rad/s); widen the range",
        },
      ],
    });
    render(<ResonanceSweepPanel />);
    await userEvent.click(sweepButton());
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("omega_min (9 rad/s) must be below omega_max (4 rad/s)");
    expect(alert).not.toHaveTextContent("Value error");
    expect(screen.queryByTestId("peak-frequency")).not.toBeInTheDocument();
    expect(sweepButton()).toBeEnabled();
  });
});

describe("ResonanceSweepPanel: the chart", () => {
  it("draws simulated points over the dashed exact curve, then the two peaks", async () => {
    await sweep();
    expect(panel().getByRole("img", { name: CHART })).toBeInTheDocument();
    const { data, layout } = charts.get(CHART)!;
    // Drawn in this order, so the numerical points lie on top of the exact line.
    expect(data.map((t) => t.name)).toEqual([
      "Exact amplitude (formula)",
      "Simulated amplitude (numerical, DOP853)",
      "Refined peak (numerical)",
      "Exact peak ω_r (formula)",
    ]);
    const [exact, simulated, refined, exactPeak] = data as [Trace, Trace, Trace, Trace];
    expect(exact.line?.dash).toBe("dash");
    expect(exact.x).toEqual([0, 5, 15]);
    expect(exact.y).toEqual([0.04, 0.2, 0.004986]);
    expect(simulated.mode).toMatch(/markers/);
    expect(simulated.x).toEqual([0.5, 5, 15]);
    expect(simulated.y).toEqual([0.040396, 0.2, 0.004986]);
    expect(refined.x).toEqual([4.9497]);
    expect(refined.y).toEqual([0.201]);
    expect(exactPeak.x).toEqual([4.949747]);
    expect(exactPeak.y).toEqual([0.2010076]);
    expect(layout.xaxis?.title?.text).toMatch(/rad\/s/);
    expect(layout.yaxis?.title?.text).toMatch(/\(m\)/);
  });

  it("names the solver that made the points (RK45 when RK45 ran)", async () => {
    await sweep({ ...BASE, solver: { ...BASE.solver, method: "RK45" } });
    expect(charts.get(CHART)!.data.map((t) => t.name)).toContain(
      "Simulated amplitude (numerical, RK45)",
    );
  });

  it("draws no exact-peak marker when there is no exact peak (zeta >= 1/sqrt 2)", async () => {
    await sweep(NO_PEAK);
    expect(charts.get(CHART)!.data.map((t) => t.name)).toEqual([
      "Exact amplitude (formula)",
      "Simulated amplitude (numerical, DOP853)",
      "Refined peak (numerical)",
    ]);
  });
});

describe("ResonanceSweepPanel: the peak", () => {
  it("shows the refined peak with its uncertainty, labelled as an estimate, and the exact w_r", async () => {
    await sweep();
    expect(screen.getByTestId("peak-frequency")).toHaveTextContent(
      /^4\.9497 ± 0\.002 rad\/s \(estimate\)$/,
    );
    expect(screen.getByTestId("peak-amplitude")).toHaveTextContent("0.201 m");
    // w_r = sqrt(24.5) = 4.949747 and A_max = 1/sqrt(24.75) = 0.2010076, to six figures.
    expect(screen.getByTestId("exact-peak-frequency")).toHaveTextContent("4.94975 rad/s");
    expect(screen.getByTestId("exact-peak-amplitude")).toHaveTextContent("0.201008 m");
    expect(panel().getByText(/Estimate, not a bound: u = 2 sqrt\(B1\/K\)/)).toBeInTheDocument();
  });

  it("labels every number beside the chart as numerical, exact or formula", async () => {
    await sweep();
    const labels = [...document.querySelectorAll("dl.stats dt")].map((dt) => dt.textContent ?? "");
    expect(labels.length).toBeGreaterThanOrEqual(5);
    for (const l of labels) expect(l).toMatch(/\((numerical|exact|formula)\)$/);
    expect(screen.getByTestId("grid-step-over-gamma")).toHaveTextContent("14.5");
  });

  it("shows no ± and the reason when u does not exist (a peak at an edge)", async () => {
    await sweep(NO_PEAK);
    const peak = screen.getByTestId("peak-frequency");
    expect(peak).toHaveTextContent(/^0\.5 rad\/s$/);
    expect(peak).not.toHaveTextContent("±");
    expect(panel().getByText(/No estimate: the best grid point is at an edge/)).toBeInTheDocument();
  });

  it("shows the exact w_r and A_max as absent, never as 0, when zeta >= 1/sqrt 2", async () => {
    await sweep(NO_PEAK);
    for (const id of ["exact-peak-frequency", "exact-peak-amplitude"]) {
      const v = screen.getByTestId(id);
      expect(v).toHaveTextContent(/^none/);
      expect(v).not.toHaveTextContent("rad/s");
      expect(v).not.toHaveTextContent(/^0\b/);
    }
  });
});

describe("ResonanceSweepPanel: checks, record and download", () => {
  it("shows the shared ChecksTable with the sweep's checks", async () => {
    await sweep();
    const c1 = screen.getByTestId("check-lock_in_amplitude");
    expect(c1).toHaveTextContent("Lock-in amplitude vs the exact A(w)");
    expect(c1).toHaveTextContent("Pass");
    expect(screen.getByTestId("check-peak_frequency")).toHaveTextContent("Pass");
    expect(screen.getByTestId("check-cost")).toHaveTextContent("Info");
    expect(panel().getByRole("columnheader", { name: "Limit" })).toBeInTheDocument();
  });

  it("shows the run record: its id and whether it was saved", async () => {
    await sweep();
    expect(panel().getByText("res-run-1")).toBeInTheDocument();
    expect(panel().getByText("Saved to experiment log").nextElementSibling).toHaveTextContent(
      "Yes",
    );
  });

  it("lists the model's assumptions", async () => {
    await sweep();
    expect(panel().getByText("Every run starts from rest.")).toBeInTheDocument();
  });

  it("offers a CSV download of the curve", async () => {
    await sweep();
    const buttons = panel().getAllByRole("button", { name: /^Download .* \(CSV\)$/ });
    expect(buttons.length).toBeGreaterThanOrEqual(1);
    expect(buttons[0]).toHaveAccessibleName(/resonance/i);
  });
});
