/**
 * The reference run (roadmap 1.6, D6 and D7): pin a run, and every later run of the same
 * model draws the reference's curves faded under its own.
 *
 * Only the boundaries are mocked: `fetch` (the API) and the Plotly library itself, which
 * needs a real browser to draw. The real PlotlyChart component runs, so each test reads the
 * exact traces a chart was handed. Every fixture below is a small hand-made response; the
 * expected curves are written out by hand, never taken from the code under test.
 */
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { StrictMode } from "react";
import { vi } from "vitest";

import { IntegratorLab } from "./IntegratorLab";
import { ProjectileLab } from "./ProjectileLab";
import { QuantLab } from "./QuantLab";
import { SolowLab } from "./SolowLab";
import PROFILE from "./fixtures/messySurveyProfile.json";

const plotly = vi.hoisted(() => ({ react: vi.fn(), purge: vi.fn() }));
vi.mock("plotly.js-dist-min", () => ({ default: plotly }));

type Trace = {
  name?: string;
  x?: unknown;
  y?: unknown;
  meta?: unknown;
  opacity?: number;
  showlegend?: boolean;
  line?: { dash?: string };
};

/** The traces most recently handed to Plotly for the chart titled `title` (still on screen). */
function drawn(title: string): Trace[] {
  const calls = plotly.react.mock.calls.filter(([el]) => {
    const node = el as HTMLElement;
    return node.isConnected && node.getAttribute("aria-label") === title;
  });
  return (calls.at(-1)?.[1] as Trace[] | undefined) ?? [];
}

const REF = "reference run";
const referenceTraces = (title: string) => drawn(title).filter((t) => t.name === REF);

/** Waits until the chart has been drawn with at least one reference trace, and returns them. */
async function drawnReference(title: string): Promise<Trace[]> {
  return waitFor(() => {
    const traces = referenceTraces(title);
    expect(traces.length).toBeGreaterThan(0);
    return traces;
  });
}

type Reply = { status?: number; body: unknown };

/** Answers `METHOD /api/v1/path` from `routes`; anything else is a 404. Returns the calls. */
function mockApi(routes: Record<string, Reply>) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const key = `${init?.method ?? "GET"} ${url}`;
      calls.push(key);
      const reply = routes[key] ?? { status: 404, body: { detail: `unexpected ${key}` } };
      return Promise.resolve(
        new Response(JSON.stringify(reply.body), {
          status: reply.status ?? 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
  return calls;
}

const outputs = (runId: string, response: unknown, digest_match: boolean | null = true) => ({
  [`POST /api/v1/experiments/${runId}/outputs`]: {
    body: { original_run_id: runId, digest_match, response },
  },
});

function openPage(path: string) {
  window.history.pushState({}, "", path);
}

const searchParam = (name: string) => new URLSearchParams(window.location.search).get(name);

afterEach(() => {
  vi.unstubAllGlobals();
  plotly.react.mockClear();
  window.history.pushState({}, "", "/");
});

// ---------- hand-made responses ----------

function metadata(run_id: string, experiment_saved: boolean) {
  return {
    run_id,
    created_at: "2026-10-24T09:00:00Z",
    input_hash: "f".repeat(64),
    output_digest: "e".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 3,
    experiment_saved,
  };
}

const metrics = { flight_time: 2, range: 20, max_height: 5, apex_time: 1, impact_speed: 14 };
const err = { absolute: 1e-12, relative: 3e-14 };

function projectile(options: {
  runId: string;
  saved?: boolean;
  version?: string;
  series: {
    t: number[];
    x: number[];
    y: number[];
    /** The solver's trajectory, when it should differ from the exact one (`x`, `y`). */
    xNumerical?: number[];
    yNumerical?: number[];
    kinetic: number[];
    potential: number[];
    drag: number[];
  };
}) {
  const s = options.series;
  return {
    model: {
      id: "physics.projectile",
      version: options.version ?? "1.0.0",
      name: "Projectile with linear drag",
      description: "",
    },
    parameters: {
      initial_speed: 20,
      launch_angle_deg: 45,
      launch_height: 0,
      mass: 1,
      drag_coefficient: 0.1,
      gravity: 9.80665,
    },
    solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
    units: { t: "s", x: "m", y: "m", energy: "J" },
    assumptions: [{ id: "point_mass", statement: "The projectile is a point mass." }],
    analytical: { ...metrics, method_note: "Exact." },
    numerical: { ...metrics, method: "DOP853", rtol: 1e-10, atol: 1e-10, n_steps: 5 },
    comparison: {
      flight_time: err,
      range: err,
      max_height: err,
      impact_speed: err,
      max_position_error: 2.2e-11,
      max_energy_balance_residual: 1.3e-12,
    },
    series: {
      t: s.t,
      x_analytical: s.x,
      y_analytical: s.y,
      x_numerical: s.xNumerical ?? s.x,
      y_numerical: s.yNumerical ?? s.y,
      speed_numerical: s.t.map(() => 1),
      kinetic_energy: s.kinetic,
      potential_energy: s.potential,
      drag_work: s.drag,
    },
    metadata: metadata(options.runId, options.saved ?? true),
  };
}

const CURRENT_SERIES = {
  t: [0, 1, 2],
  x: [0, 10, 20],
  y: [0, 5, 0],
  kinetic: [200, 150, 190],
  potential: [0, 49, 0],
  drag: [0, 1, 10],
};
const REFERENCE_SERIES = {
  t: [0, 0.5, 1],
  x: [0, 3, 6],
  y: [0, 2, 0],
  // Not the exact curve (a loose tolerance, say): the reference draws what its solver computed.
  xNumerical: [0, 3.25, 6.5],
  yNumerical: [0, 2.25, 0.5],
  kinetic: [8, 2, 8],
  potential: [0, 6, 0],
  drag: [0, 0, 0],
};

const CURRENT = projectile({ runId: "current-run", series: CURRENT_SERIES });
// A recomputation has its own new run id; the reference keeps the stored one.
const REFERENCE = projectile({ runId: "recomputed", saved: false, series: REFERENCE_SERIES });

const TRAJECTORY = "Trajectory: height against horizontal distance";
const ENERGY = "Energy against time";

const SIMULATE = "POST /api/v1/physics/projectile/simulate";
const runSimulation = () => userEvent.click(screen.getByRole("button", { name: "Run simulation" }));

describe("pinning a run as the reference run", () => {
  it("puts a saved run's id in the URL as ?ref= and draws it under the run", async () => {
    const calls = mockApi({ [SIMULATE]: { body: CURRENT } });
    openPage("/physics/projectile");
    render(<ProjectileLab />);
    await runSimulation();
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));

    expect(searchParam("ref")).toBe("current-run");
    expect(screen.getByText(/computed in this session/)).toBeInTheDocument();
    const [trace] = await drawnReference(TRAJECTORY);
    expect(trace!.x).toEqual([0, 10, 20]);
    expect(trace!.y).toEqual([0, 5, 0]);
    // Pinned from the screen: nothing is recomputed.
    expect(calls.some((c) => c.includes("/outputs"))).toBe(false);
  });

  it("pins an unsaved run in memory only, labelled as lost on reload", async () => {
    mockApi({ [SIMULATE]: { body: { ...CURRENT, metadata: metadata("unsaved-run", false) } } });
    openPage("/physics/projectile");
    render(<ProjectileLab />);
    await runSimulation();
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));

    expect(screen.getByText(/lost on reload/)).toBeInTheDocument();
    expect(searchParam("ref")).toBeNull();
    const [trace] = await drawnReference(TRAJECTORY);
    expect(trace!.x).toEqual([0, 10, 20]);
  });

  it("unpins: the reference trace and ?ref= both go", async () => {
    mockApi({ ...outputs("ref-run-1", REFERENCE), [SIMULATE]: { body: CURRENT } });
    openPage("/physics/projectile?ref=ref-run-1");
    render(<ProjectileLab />);
    await runSimulation();
    await drawnReference(TRAJECTORY);

    await userEvent.click(screen.getByRole("button", { name: "Unpin reference run" }));
    expect(searchParam("ref")).toBeNull();
    // Both charts had reference traces, so this passes only once they are redrawn without.
    await waitFor(() => expect(referenceTraces(TRAJECTORY)).toEqual([]));
    await waitFor(() => expect(referenceTraces(ENERGY)).toEqual([]));
    expect(drawn(TRAJECTORY).length).toBeGreaterThan(0);
  });
});

describe("a slow recomputation never undoes a newer choice", () => {
  /** Like mockApi, but the /outputs reply waits until `release` is called. */
  function mockSlowOutputs() {
    let release: () => void = () => {};
    const gate = new Promise<void>((resolve) => (release = resolve));
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        const json = (body: unknown) =>
          new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } });
        if (url.endsWith("/outputs")) {
          await gate;
          return json({ original_run_id: "slow-ref", digest_match: true, response: REFERENCE });
        }
        if (init?.method === "POST" && url.endsWith("/simulate")) return json(CURRENT);
        return new Response("{}", { status: 404 });
      }),
    );
    return () => release();
  }

  it("unpinned while recomputing: stays unpinned", async () => {
    const release = mockSlowOutputs();
    openPage("/physics/projectile?ref=slow-ref");
    render(<ProjectileLab />);
    expect(await screen.findByText(/Recomputing reference run slow-ref/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Unpin reference run" }));
    release();
    await runSimulation();
    await waitFor(() => expect(drawn(TRAJECTORY).length).toBeGreaterThan(0));
    expect(screen.queryByTestId("reference-provenance")).toBeNull();
    expect(referenceTraces(TRAJECTORY)).toEqual([]);
    expect(searchParam("ref")).toBeNull();
  });

  it("survives React StrictMode's doubled effects (the first request is ignored)", async () => {
    const release = mockSlowOutputs();
    openPage("/physics/projectile?ref=slow-ref");
    render(
      <StrictMode>
        <ProjectileLab />
      </StrictMode>,
    );
    release();
    expect(await screen.findByText("recomputed, bit-identical")).toBeInTheDocument();
    expect(screen.queryByText(/Recomputing reference run/)).toBeNull();
  });

  it("another run pinned while recomputing: that run stays the reference", async () => {
    const release = mockSlowOutputs();
    openPage("/physics/projectile?ref=slow-ref");
    render(<ProjectileLab />);
    await runSimulation();
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));
    release();
    // Give the released recomputation time to settle before checking it changed nothing.
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.getByTestId("reference-provenance")).toHaveTextContent(
      /computed in this session/,
    );
    expect(searchParam("ref")).toBe("current-run");
    const [trace] = await drawnReference(TRAJECTORY);
    expect(trace!.x).toEqual([0, 10, 20]);
  });
});

describe("opening a page with ?ref=", () => {
  it("recomputes the reference and draws its curves faded, under the current run's", async () => {
    const calls = mockApi({ ...outputs("ref-run-1", REFERENCE), [SIMULATE]: { body: CURRENT } });
    openPage("/physics/projectile?ref=ref-run-1");
    render(<ProjectileLab />);
    expect(await screen.findByText("recomputed, bit-identical")).toBeInTheDocument();
    expect(calls).toContain("POST /api/v1/experiments/ref-run-1/outputs");
    await runSimulation();

    // The reference's own numerical trajectory, like its energies (also from the solver).
    const [trajectory] = await drawnReference(TRAJECTORY);
    expect(trajectory!.x).toEqual([0, 3.25, 6.5]);
    expect(trajectory!.y).toEqual([0, 2.25, 0.5]);
    expect(trajectory!.opacity).toBeLessThan(1);
    expect(trajectory!.line?.dash).toBe("dash");
    // Drawn first, so the current run's curves lie on top.
    expect(drawn(TRAJECTORY)[0]!.name).toBe(REF);

    const energy = await drawnReference(ENERGY);
    expect(energy.map((t) => t.y)).toEqual([
      [8, 2, 8],
      [0, 6, 0],
      [0, 0, 0],
    ]);
    for (const t of energy) expect(t.x).toEqual([0, 0.5, 1]);
    // One legend entry for the reference, however many curves it has.
    expect(energy.filter((t) => t.showlegend !== false)).toHaveLength(1);
  });

  it("keeps ?run= working beside ?ref=, and URL-encodes the reference's id", async () => {
    const reopened = {
      run_id: "reopened-run",
      model_id: "physics.projectile",
      model_version: "1.0.0",
      created_at: "2026-10-23T10:00:00+00:00",
      input_hash: "a".repeat(64),
      inputs: { parameters: { initial_speed: 33 } },
      summary: {},
      environment: {},
      record_version: 2,
      output_digest: "b".repeat(64),
      replay_of: null,
      lab: "physics",
      headline: "h",
    };
    const calls = mockApi({
      "GET /api/v1/experiments/reopened-run": { body: reopened },
      // "a/b?c" as one path segment: the slash and question mark are percent-encoded.
      [`POST /api/v1/experiments/a%2Fb%3Fc/outputs`]: {
        body: { original_run_id: "a/b?c", digest_match: true, response: REFERENCE },
      },
      [SIMULATE]: { body: CURRENT },
    });
    openPage("/physics/projectile?run=reopened-run&ref=a%2Fb%3Fc");
    render(<ProjectileLab />);
    expect(await screen.findByText(/Loaded the inputs of run reopene/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Initial speed/)).toHaveValue("33");
    expect(await screen.findByText("recomputed, bit-identical")).toBeInTheDocument();
    expect(calls).toContain("POST /api/v1/experiments/a%2Fb%3Fc/outputs");

    await runSimulation();
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));
    expect(searchParam("ref")).toBe("current-run");
    expect(searchParam("run")).toBe("reopened-run");
    await userEvent.click(screen.getByRole("button", { name: "Unpin reference run" }));
    expect(searchParam("ref")).toBeNull();
    expect(searchParam("run")).toBe("reopened-run");
  });

  it.each([
    [true, "recomputed, bit-identical"],
    [
      false,
      "recomputed, not bit-identical (cause not checked; usually another CPU or library version)",
    ],
    [null, "recomputed; cannot be checked (older record without a digest)"],
  ])("labels the reference's provenance (digest_match %s)", async (digest, label) => {
    mockApi(outputs("ref-run-1", REFERENCE, digest));
    openPage("/physics/projectile?ref=ref-run-1");
    render(<ProjectileLab />);
    expect(await screen.findByText(label)).toBeInTheDocument();
  });

  it.each([
    [409, "This run used physics.projectile v0.9.0; the current version is v1.0.0."],
    [422, "To rerun quant.dataset_profile, supply the file again."],
    [404, "No experiment with run_id 'gone'"],
  ])("shows a %s refusal clearly, and the page still works", async (status, detail) => {
    mockApi({
      "POST /api/v1/experiments/gone/outputs": { status, body: { detail } },
      [SIMULATE]: { body: CURRENT },
    });
    openPage("/physics/projectile?ref=gone");
    render(<ProjectileLab />);
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/reference run gone/i);
    expect(alert).toHaveTextContent(detail);

    await runSimulation();
    expect(await screen.findByText("Analytical vs numerical")).toBeInTheDocument();
    await waitFor(() => expect(drawn(TRAJECTORY).length).toBeGreaterThan(0));
    expect(referenceTraces(TRAJECTORY)).toEqual([]);
  });

  it("refuses to overlay a reference from another model, with a message", async () => {
    mockApi({ ...outputs("solow-run", solow("x", 1)), [SIMULATE]: { body: CURRENT } });
    openPage("/physics/projectile?ref=solow-run");
    render(<ProjectileLab />);
    expect(await screen.findByText(/economy\.solow run/)).toBeInTheDocument();
    expect(screen.getByText(/only over runs of the same model/)).toBeInTheDocument();

    await runSimulation();
    await waitFor(() => expect(drawn(TRAJECTORY).length).toBeGreaterThan(0));
    expect(referenceTraces(TRAJECTORY)).toEqual([]);
    expect(referenceTraces(ENERGY)).toEqual([]);
  });

  it("warns when the reference ran on another version of the model, and still overlays", async () => {
    const older = projectile({ runId: "r", version: "0.9.0", series: REFERENCE_SERIES });
    mockApi({ ...outputs("ref-old", older), [SIMULATE]: { body: CURRENT } });
    openPage("/physics/projectile?ref=ref-old");
    render(<ProjectileLab />);
    await runSimulation();

    expect(await screen.findByText(/v0\.9\.0.*v1\.0\.0/)).toHaveTextContent(/version/);
    const [trace] = await drawnReference(TRAJECTORY);
    expect(trace!.x).toEqual([0, 3.25, 6.5]);
  });
});

// ---------- the other chart-bearing models ----------

function sweep(runId: string, angles: number[], ranges: number[]) {
  return {
    model: { id: "physics.projectile.angle_sweep", version: "1.0.0", name: "Sweep" },
    parameters: CURRENT.parameters,
    units: { angle: "deg", range: "m", flight_time: "s", max_height: "m" },
    angles_deg: angles,
    ranges,
    flight_times: angles.map(() => 1),
    max_heights: angles.map(() => 1),
    best_angle_deg: 40,
    best_range: 9,
    vacuum_best_angle_deg: 45,
    vacuum_best_range: 40.79,
    method_note: "Exact.",
    metadata: metadata(runId, true),
  };
}

it("overlays a reference angle sweep on the sweep chart", async () => {
  mockApi({
    ...outputs("ref-sweep", sweep("recomputed", [0, 30, 60, 90], [0, 7, 6, 0])),
    [SIMULATE]: { body: CURRENT },
    "POST /api/v1/physics/projectile/angle-sweep": {
      body: sweep("sweep-now", [0, 45, 90], [0, 12, 0]),
    },
  });
  openPage("/physics/projectile?ref=ref-sweep");
  render(<ProjectileLab />);
  await runSimulation();
  await userEvent.click(await screen.findByRole("button", { name: "Sweep launch angle" }));

  const [trace] = await drawnReference("Range against launch angle");
  expect(trace!.x).toEqual([0, 30, 60, 90]);
  expect(trace!.y).toEqual([0, 7, 6, 0]);
  // A sweep is not a trajectory: nothing is drawn on the projectile's own charts.
  expect(referenceTraces(TRAJECTORY)).toEqual([]);
});

function studyRun(h: number, error: number | null) {
  return {
    dt_requested: h,
    h,
    n_steps: Math.round(2 / h),
    kh: h,
    amplification_factor: 1 - h,
    stability: error === null ? "unstable" : "stable",
    diverged: error === null,
    n_completed: Math.round(2 / h),
    max_position_error: error,
    max_velocity_error: error === null ? null : error * 2,
    final_position_error: error,
    final_velocity_error: error,
    position_roundoff_floor: 1e-12,
    velocity_roundoff_floor: 1e-12,
    in_position_fit: error !== null,
    in_velocity_fit: error !== null,
    exclusion_reason: error === null ? "diverged" : null,
  };
}

function study(runId: string, errors: (number | null)[], exact: { x: number[]; y: number[] }) {
  const fit = {
    order: 1,
    theoretical_order: 1,
    r_squared: 1,
    n_points: 2,
    h_min: 0.05,
    h_max: 0.1,
  };
  return {
    model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study" },
    parameters: CURRENT.parameters,
    dt_values: [0.2, 0.1, 0.05],
    methods: ["euler"],
    units: { h: "s", position_error: "m", velocity_error: "m/s", x: "m", y: "m" },
    assumptions: [{ id: "fixed_horizon", statement: "Fixed horizon." }],
    horizon: 2,
    k: 1,
    position_scale: 10,
    velocity_scale: 20,
    fit_rule: {
      max_kh: 0.2,
      max_h_over_horizon: 0.05,
      roundoff_safety_factor: 100,
      min_points: 2,
      description: "Rule.",
    },
    results: [
      {
        method: "euler",
        name: "Forward Euler",
        theoretical_order: 1,
        stability_limit_kh: 2,
        runs: [0.2, 0.1, 0.05].map((h, i) => studyRun(h, errors[i]!)),
        position_local_orders: [1],
        velocity_local_orders: [1],
        position_fit: fit,
        velocity_fit: fit,
        position_reference: null,
        velocity_reference: null,
        fit_note: null,
        trajectory: { h: 0.1, x: exact.x, y: exact.y },
      },
    ],
    exact_trajectory: exact,
    metadata: metadata(runId, true),
  };
}

it("overlays a reference integrator study on its convergence and trajectory charts", async () => {
  mockApi({
    // The coarsest step diverged in the reference: it has no error to draw.
    ...outputs("ref-study", study("recomputed", [null, 0.4, 0.2], { x: [0, 4, 8], y: [0, 3, 0] })),
    "POST /api/v1/physics/projectile/integrators": {
      body: study("study-now", [1, 0.5, 0.25], { x: [0, 5, 10], y: [0, 4, 0] }),
    },
  });
  openPage("/physics/projectile/integrators?ref=ref-study");
  render(<IntegratorLab />);
  await userEvent.click(screen.getByRole("button", { name: "Run study" }));

  const [position] = await drawnReference(
    "Log-log convergence plot of maximum position error against time step",
  );
  expect(position!.x).toEqual([0.1, 0.05]);
  expect(position!.y).toEqual([0.4, 0.2]);
  const [velocity] = await drawnReference(
    "Log-log convergence plot of maximum velocity error against time step",
  );
  expect(velocity!.y).toEqual([0.8, 0.4]);
  const [exact] = await drawnReference(
    "Trajectories from each method compared with the exact solution",
  );
  expect(exact!.x).toEqual([0, 4, 8]);
  expect(exact!.y).toEqual([0, 3, 0]);
});

function solow(runId: string, scale: number) {
  const path = (capital: number[]) => ({
    savings_rate: [0.2, 0.3, 0.3],
    capital,
    output: [1, 1.1, 1.2],
    consumption: capital.map((k) => k / 4),
    investment: [0.2, 0.33, 0.36],
    output_per_worker_index: [100, 103 * scale, 106 * scale],
    output_per_worker_growth: [0.03, 0.028],
  });
  const steady = { savings_rate: 0.2, capital: 3, output: 1.4, consumption: 1.1 };
  return {
    model: { id: "economy.solow", version: "1.0.0", name: "Solow growth model" },
    parameters: { capital_share: 0.3 },
    policy: { new_savings_rate: 0.3, policy_year: 1 },
    horizon_years: 2,
    units: { years: "year", capital: "capital per effective worker (model units)" },
    assumptions: [{ id: "cobb_douglas", statement: "Production is Cobb-Douglas." }],
    years: [0, 1, 2],
    baseline: path([2 * scale, 2.5 * scale, 3 * scale]),
    scenario: path([2 * scale, 2.7 * scale, 3.4 * scale]),
    baseline_steady_state: { ...steady, capital_output_ratio: 2.5 },
    scenario_steady_state: { ...steady, capital_output_ratio: 3.7 },
    golden_rule: { ...steady, capital_output_ratio: 3.7 },
    convergence: {
      effective_depreciation: 0.08,
      growth_factor: 1.03,
      rho: 0.95,
      one_minus_rho: 0.05,
      half_life_years: 12.4,
    },
    initial_capital: 1,
    checks: [],
    method_note: "Exact recurrence.",
    metadata: metadata(runId, true),
  };
}

it("overlays a reference Solow run's baseline and scenario on each chart", async () => {
  mockApi({
    ...outputs("ref-solow", solow("recomputed", 1)),
    "POST /api/v1/economy/solow/simulate": { body: solow("solow-now", 2) },
  });
  openPage("/economy/solow?ref=ref-solow");
  render(<SolowLab />);
  await userEvent.click(screen.getByRole("button", { name: "Run model" }));

  const capital = await drawnReference("Capital per effective worker over time");
  expect(capital.map((t) => t.y)).toEqual([
    [2, 2.5, 3],
    [2, 2.7, 3.4],
  ]);
  for (const t of capital) expect(t.x).toEqual([0, 1, 2]);
  const consumption = await drawnReference("Consumption per effective worker over time");
  expect(consumption.map((t) => t.y)).toEqual([
    [0.5, 0.625, 0.75],
    [0.5, 0.675, 0.85],
  ]);
  const perWorker = await drawnReference("Output per actual worker, index");
  expect(perWorker.map((t) => t.y)).toEqual([
    [100, 103, 106],
    [100, 103, 106],
  ]);
});

// ---------- the dataset profile: pinned, never overlaid ----------

const SAMPLES = [{ id: "messy_survey", title: "Survey", description: "" }];

describe("the dataset profile", () => {
  it("pins a saved sample profile as ?ref= but draws no overlay", async () => {
    mockApi({
      "GET /api/v1/quant/datasets/samples": { body: SAMPLES },
      "POST /api/v1/quant/datasets/profile": {
        body: { ...PROFILE, metadata: { ...PROFILE.metadata, experiment_saved: true } },
      },
    });
    openPage("/quant/datasets");
    render(<QuantLab />);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));

    expect(searchParam("ref")).toBe("fixture-run");
    await waitFor(() => expect(plotly.react).toHaveBeenCalled());
    for (const [, data] of plotly.react.mock.calls) {
      expect((data as Trace[]).filter((t) => t.name === REF)).toEqual([]);
    }
  });

  it("keeps an uploaded file's profile in memory only, even when saved", async () => {
    mockApi({
      "GET /api/v1/quant/datasets/samples": { body: SAMPLES },
      "POST /api/v1/quant/datasets/profile": {
        body: {
          ...PROFILE,
          dataset: { ...PROFILE.dataset, source: "upload", sample_id: null },
          metadata: { ...PROFILE.metadata, experiment_saved: true },
        },
      },
    });
    openPage("/quant/datasets");
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    await userEvent.upload(screen.getByLabelText(/^CSV file/), new File(["a\n1\n"], "d.csv"));
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));

    expect(screen.getByText(/lost on reload/)).toBeInTheDocument();
    expect(searchParam("ref")).toBeNull();
  });
});
