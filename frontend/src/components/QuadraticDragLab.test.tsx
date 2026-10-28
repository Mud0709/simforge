import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { QuadraticDragResponse } from "@/lib/api/client";
import { QuadraticDragLab } from "./QuadraticDragLab";

// Plotly needs a real browser; the E2E test draws the charts. Here each chart's traces are
// recorded by title, so a test can read what would be drawn.
type Trace = { name?: string; x?: number[]; y?: number[]; line?: { dash?: string } };
const charts = new Map<string, Trace[]>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, data }: { title: string; data: Trace[] }) => {
    charts.set(title, data);
    return <div role="img" aria-label={title} />;
  },
}));

// A small hand-made response: only the shape matters here, not the physics. The values are
// typed by hand (none is produced by the code under test).
const err = (absolute: number, relative: number | null) => ({ absolute, relative });
const check = (id: string, label: string, value: number, threshold: number | null) => ({
  id,
  label,
  value,
  threshold,
  passed: threshold === null ? null : value <= threshold,
  kind: threshold === null ? "informational" : "numerical_diagnostic",
  note: `${label} note`,
});
const BASE = {
  model: {
    id: "physics.projectile.quadratic_drag",
    version: "1.0.0",
    name: "Projectile motion with quadratic drag",
    description: "",
  },
  parameters: {
    initial_speed: 20,
    launch_angle_deg: 45,
    launch_height: 0,
    mass: 1,
    drag_constant: 0.01,
    gravity: 9.80665,
  },
  solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
  units: { t: "s", x: "m", y: "m", speed: "m/s", energy: "J" },
  assumptions: [{ id: "quadratic_drag", statement: "Drag is quadratic in speed, F = -c|v|v." }],
  numerical: {
    flight_time: 2.4,
    range: 30.5,
    max_height: 8.2,
    apex_time: 1.15,
    impact_speed: 16.9,
    method: "DOP853",
    rtol: 1e-10,
    atol: 1e-10,
    n_steps: 31,
    n_rhs_evaluations: 420,
  },
  numerical_note: "numerical: adaptive Runge-Kutta solve (SciPy solve_ivp)",
  terminal_speed: 31.3,
  vacuum: {
    flight_time: 2.88,
    range: 40.79,
    max_height: 10.19,
    apex_time: 1.44,
    impact_speed: 20,
    method_note: "exact: the same launch with no drag, from the textbook closed forms",
  },
  vertical_reference: null,
  diagnostics: {
    max_energy_balance_residual: 3.4e-13,
    max_invariant_residual: 5.6e-12,
    invariant_note: "Invariant note.",
    drag_time_bound: 0.41,
    flight_time_bound: 7.5,
  },
  checks: [
    check("energy_balance", "Energy balance KE + PE + W = E0", 3.4e-13, 1e-6),
    check("hodograph_invariant", "Hodograph invariant I is constant", 5.6e-12, 1e-6),
    check("drag_time", "Drag time (upper bound)", 0.41, null),
  ],
  series: {
    t: [0, 1.2, 2.4],
    x: [0, 15, 30.5],
    y: [0, 8, 0],
    speed: [20, 12, 16.9],
    kinetic_energy: [200, 72, 142.8],
    potential_energy: [0, 78.5, 0],
    drag_work: [0, 49.5, 57.2],
    vacuum_t: [0, 1.44, 2.88],
    vacuum_x: [0, 20.4, 40.79],
    vacuum_y: [0, 10.19, 0],
  },
  metadata: {
    run_id: "q-run-1",
    created_at: "2026-01-01T00:00:00Z",
    input_hash: "f".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 3,
    experiment_saved: true,
  },
};
const RESPONSE = BASE as unknown as QuadraticDragResponse;

/** A vertical launch in a vacuum: the exact vertical reference is present, v_t and I are not. */
const VERTICAL_VACUUM = {
  ...BASE,
  parameters: { ...BASE.parameters, launch_angle_deg: 90, drag_constant: 0 },
  terminal_speed: null,
  vertical_reference: {
    exact: {
      apex_time: 2.0394,
      max_height: 20.394,
      fall_time: 2.0394,
      flight_time: 4.0788,
      impact_speed: 20,
    },
    flight_time: err(2e-12, 4.9e-13),
    apex_time: err(1e-12, 4.9e-13),
    max_height: err(3e-11, 1.5e-12),
    impact_speed: err(0, 0),
    method_note: "exact: the vertical flight with quadratic drag, rising with tan",
  },
  diagnostics: {
    ...BASE.diagnostics,
    max_invariant_residual: null,
    invariant_note: "Undefined for a vertical launch: the invariant divides by vx = 0.",
  },
  checks: [
    check("vertical_flight_time", "Flight time vs the exact vertical flight", 4.9e-13, 1e-6),
    check("hodograph_invariant", "Hodograph invariant (not available)", 0, null),
  ],
} as unknown as QuadraticDragResponse;

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

async function run(body: unknown = RESPONSE) {
  const fetchMock = mockFetch(200, body);
  await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
  await screen.findByText(/Run complete/);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
  charts.clear();
});

describe("QuadraticDragLab", () => {
  it("builds its fields from the OpenAPI schema, with units and the backend's defaults", () => {
    render(<QuadraticDragLab />);
    const params = region("Parameters");
    // Defaults typed from backend/src/simforge/physics/projectile/quadratic_schemas.py and
    // SolverSettings in schemas.py.
    const expected: [RegExp, string, string][] = [
      [/^Initial speed/, "m/s", "20"],
      [/^Launch angle/, "°", "45"],
      [/^Launch height/, "m", "0"],
      [/^Mass/, "kg", "1"],
      [/^Drag constant c/, "kg/m", "0.01"],
      [/^Gravity/, "m/s²", "9.80665"],
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
    // The field's description says which "drag" constant this is.
    expect(params.getByLabelText(/^Drag constant c/)).toHaveAttribute(
      "title",
      expect.stringContaining("Not the dimensionless drag coefficient C_d"),
    );
    expect(params.getByLabelText("Method")).toHaveValue("DOP853");
    // No linear-drag field on this page.
    expect(params.queryByLabelText(/^Drag coefficient b/)).not.toBeInTheDocument();
  });

  it("sends the form to the quadratic-drag endpoint and shows the results", async () => {
    render(<QuadraticDragLab />);
    const c = screen.getByLabelText(/^Drag constant c/);
    await userEvent.clear(c);
    await userEvent.type(c, "0.02");
    await userEvent.selectOptions(screen.getByLabelText("Method"), "Radau");
    const fetchMock = await run();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/projectile/quadratic-drag/simulate");
    const sent = JSON.parse(init.body);
    expect(sent.parameters).toEqual({
      initial_speed: 20,
      launch_angle_deg: 45,
      launch_height: 0,
      mass: 1,
      drag_constant: 0.02,
      gravity: 9.80665,
    });
    expect(sent.solver).toEqual({ method: "Radau", rtol: 1e-10, atol: 1e-10 });

    // Results: numerical values labelled numerical, the terminal speed labelled exact.
    const results = region("Results");
    expect(results.getByText("Range (numerical)").nextSibling).toHaveTextContent("30.5 m");
    expect(results.getByText("Flight time (numerical)").nextSibling).toHaveTextContent("2.4 s");
    expect(results.getByText("Terminal speed v_t (exact)").nextSibling).toHaveTextContent(
      "31.3 m/s",
    );
    expect(results.getByText(/adaptive Runge-Kutta solve/)).toHaveTextContent(
      "DOP853, rtol = 1e-10, atol = 1e-10",
    );
    // The same launch without drag, side by side.
    const rangeRow = results.getByRole("row", { name: /^Range/ });
    expect(rangeRow).toHaveTextContent("30.5");
    expect(rangeRow).toHaveTextContent("40.79");
    expect(results.getByText(/textbook closed forms/)).toBeInTheDocument();
    for (const table of ["trajectory", "speed", "energy budget"]) {
      expect(results.getByRole("button", { name: `Download ${table} (CSV)` })).toBeInTheDocument();
    }
    // Assumptions and the run record.
    expect(
      region("Assumptions").getByText("Drag is quadratic in speed, F = -c|v|v."),
    ).toBeInTheDocument();
    expect(region("Validation").getByText("q-run-1")).toBeInTheDocument();
  });

  it("draws the trajectory over the drag-free one, speed with v_t, and the energy budget", async () => {
    render(<QuadraticDragLab />);
    await run();
    const vis = region("Visualisation");
    for (const name of [
      "Trajectory: height against horizontal distance",
      "Speed against time",
      "Energy against time",
    ]) {
      expect(vis.getByRole("img", { name })).toBeInTheDocument();
    }

    const trajectory = charts.get("Trajectory: height against horizontal distance")!;
    expect(trajectory.map((t) => t.name)).toEqual([
      "Quadratic drag (numerical, DOP853)",
      "No drag (exact)",
    ]);
    expect(trajectory[0]!.x).toEqual([0, 15, 30.5]);
    expect(trajectory[1]!.x).toEqual([0, 20.4, 40.79]);
    expect(trajectory[1]!.line?.dash).toBe("dash");

    const speed = charts.get("Speed against time")!;
    expect(speed.map((t) => t.name)).toEqual(["Speed (numerical)", "Terminal speed v_t (exact)"]);
    expect(speed[0]!.y).toEqual([20, 12, 16.9]);
    // A horizontal line at v_t across the flight.
    expect(speed[1]!.x).toEqual([0, 2.4]);
    expect(speed[1]!.y).toEqual([31.3, 31.3]);

    const energy = charts.get("Energy against time")!;
    expect(energy.map((t) => t.name)).toEqual([
      "Kinetic",
      "Potential",
      "Work against drag",
      "KE + PE + W (constant for the true motion)",
    ]);
    // 200 + 0 + 0, 72 + 78.5 + 49.5, 142.8 + 0 + 57.2: all 200 J.
    expect(energy[3]!.y).toEqual([200, 200, 200]);
  });

  it("shows the checks with their labels under Validation", async () => {
    render(<QuadraticDragLab />);
    await run();
    const validation = region("Validation");
    const energy = validation.getByTestId("check-energy_balance");
    expect(energy).toHaveTextContent("Energy balance KE + PE + W = E0");
    expect(energy).toHaveTextContent("Pass");
    expect(validation.getByTestId("check-hodograph_invariant")).toHaveTextContent(
      "Hodograph invariant I is constant",
    );
    expect(validation.getByTestId("check-drag_time")).toHaveTextContent("Info");
    expect(validation.getByText("Hodograph invariant residual").nextSibling).toHaveTextContent(
      "5.6e-12",
    );
    // No exact vertical comparison for a 2-D launch, and it says why.
    expect(validation.queryByText("Exact vertical flight vs numerical")).not.toBeInTheDocument();
    expect(validation.getByText(/only for a launch at exactly 90°/)).toBeInTheDocument();
  });

  it("shows a vertical launch in a vacuum: the exact vertical flight, no v_t, no invariant", async () => {
    render(<QuadraticDragLab />);
    await run(VERTICAL_VACUUM);

    const results = region("Results");
    expect(results.getByText("Terminal speed v_t").nextSibling).toHaveTextContent(
      "none: no drag (c = 0)",
    );
    const speed = charts.get("Speed against time")!;
    expect(speed.map((t) => t.name)).toEqual(["Speed (numerical)"]);
    expect(region("Visualisation").getByText(/no terminal speed in a vacuum/i)).toBeInTheDocument();

    const validation = region("Validation");
    expect(validation.getByText("Exact vertical flight vs numerical")).toBeInTheDocument();
    const flight = validation.getByRole("row", { name: /^Flight time \(s\)/ });
    expect(flight).toHaveTextContent("4.0788"); // exact
    expect(flight).toHaveTextContent("2.4"); // numerical
    expect(flight).toHaveTextContent("4.9e-13");
    expect(validation.getByText(/rising with tan/)).toBeInTheDocument();
    expect(validation.getByText("Hodograph invariant residual").nextSibling).toHaveTextContent(
      "not available",
    );
    expect(validation.getByText(/divides by vx = 0/)).toBeInTheDocument();
    expect(validation.getByTestId("check-hodograph_invariant")).toHaveTextContent(
      "Hodograph invariant (not available)",
    );
  });

  it("marks the results as out of date when an input changes, until the next run", async () => {
    render(<QuadraticDragLab />);
    await run();
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
    const c = screen.getByLabelText(/^Drag constant c/);
    await userEvent.type(c, "5");
    expect(region("Validation").getByText(/inputs have changed/)).toBeInTheDocument();
    await userEvent.type(c, "{backspace}");
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
  });

  it("blocks invalid input without calling the API", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<QuadraticDragLab />);
    const c = screen.getByLabelText(/^Drag constant c/);
    await userEvent.clear(c);
    await userEvent.type(c, "-1");
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(screen.getByText("Must be ≥ 0")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server's reason when it refuses a run (the atol rule)", async () => {
    // FastAPI's 422 body for a request-level rule: loc is just ["body"].
    mockFetch(422, {
      detail: [
        {
          loc: ["body"],
          msg:
            "Value error, atol = 0.5 is above 0.01 x min(v0, v_t), the smallest velocity " +
            "scale, here the launch speed v0 = 20 m/s (terminal speed v_t = 31.3 m/s): the " +
            "solver would not control the velocity, and the run can be very slow; use atol <= 0.2",
        },
      ],
    });
    render(<QuadraticDragLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/^atol = 0\.5 is above 0\.01 x min\(v0, v_t\)/);
    expect(alert).toHaveTextContent("use atol <= 0.2");
    expect(alert).not.toHaveTextContent("Value error");
    expect(region("Results").queryByText("Range (numerical)")).not.toBeInTheDocument();
  });
});
