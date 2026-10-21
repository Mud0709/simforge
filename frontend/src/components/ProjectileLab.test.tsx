import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { ProjectileResponse } from "@/lib/api/client";
import { ProjectileLab } from "./ProjectileLab";

// Plotly needs a real browser (canvas, SVG layout); charts are covered by the E2E test.
// Each chart's layout object is recorded so a test can check that typing does not redraw.
const layouts = new Map<string, unknown[]>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, layout }: { title: string; layout: unknown }) => {
    layouts.set(title, [...(layouts.get(title) ?? []), layout]);
    return <div role="img" aria-label={title} />;
  },
}));

const metrics = {
  flight_time: 2.9,
  range: 36.4,
  max_height: 9.9,
  apex_time: 1.4,
  impact_speed: 18,
};
const err = { absolute: 1e-12, relative: 3e-14 };
const RESPONSE = {
  model: { id: "physics.projectile", version: "1.0.0", name: "Projectile", description: "" },
  parameters: {},
  solver: { method: "DOP853", rtol: 1e-10, atol: 1e-10 },
  units: {},
  assumptions: [{ id: "point_mass", statement: "The projectile is a point mass." }],
  analytical: { ...metrics, method_note: "Exact." },
  numerical: {
    ...metrics,
    method: "DOP853",
    rtol: 1e-10,
    atol: 1e-10,
    n_steps: 5,
    n_rhs_evaluations: 70,
  },
  comparison: {
    flight_time: err,
    range: err,
    max_height: err,
    impact_speed: err,
    max_position_error: 2.2e-11,
    max_energy_balance_residual: 1.3e-12,
  },
  series: {
    t: [0, 1],
    x_numerical: [0, 1],
    y_numerical: [0, 1],
    x_analytical: [0, 1],
    y_analytical: [0, 1],
    speed_numerical: [1, 1],
    kinetic_energy: [1, 1],
    potential_energy: [0, 0],
    drag_work: [0, 0],
  },
  metadata: {
    run_id: "abc",
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
} as unknown as ProjectileResponse;

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

afterEach(() => vi.unstubAllGlobals());

describe("ProjectileLab", () => {
  it("lays out the five workspace sections before any run", () => {
    render(<ProjectileLab />);
    for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
    const params = screen.getByRole("region", { name: "Parameters" });
    expect(within(params).getByLabelText(/^Mass/)).toBeInTheDocument();
    expect(within(params).getByRole("button", { name: "Run simulation" })).toBeInTheDocument();
  });

  it("puts each part of the result in its workspace section", async () => {
    mockFetch(200, RESPONSE);
    render(<ProjectileLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));

    const region = (name: string) => screen.getByRole("region", { name });
    await screen.findByText("Analytical vs numerical");
    // Visualisation: both charts, nothing else numeric.
    const vis = within(region("Visualisation"));
    expect(vis.getByRole("img", { name: /Trajectory/ })).toBeInTheDocument();
    expect(vis.getByRole("img", { name: "Energy against time" })).toBeInTheDocument();
    expect(vis.queryByText("Range (analytical)")).not.toBeInTheDocument();
    expect(vis.queryByTestId("max-position-error")).not.toBeInTheDocument();
    expect(vis.queryByText("Analytical vs numerical")).not.toBeInTheDocument();
    // Results: the exact quantities and the angle sweep.
    const results = within(region("Results"));
    expect(results.getByText("Range (analytical)")).toBeInTheDocument();
    expect(results.getByRole("button", { name: "Sweep launch angle" })).toBeInTheDocument();
    // Validation: the exact-vs-numerical comparison and the run record.
    const validation = within(region("Validation"));
    expect(validation.getByText("Analytical vs numerical")).toBeInTheDocument();
    expect(validation.getByTestId("max-position-error")).toHaveTextContent("2.2e-11 m");
    expect(validation.getByText("Reproducibility")).toBeInTheDocument();
    // Assumptions.
    expect(
      within(region("Assumptions")).getByText("The projectile is a point mass."),
    ).toBeInTheDocument();
  });

  it("marks the results as out of date when an input changes, until the next run", async () => {
    mockFetch(200, RESPONSE);
    render(<ProjectileLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    await screen.findByText("Analytical vs numerical");
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();

    const drag = screen.getByLabelText(/^Drag coefficient/);
    await userEvent.type(drag, "5");
    expect(
      within(screen.getByRole("region", { name: "Validation" })).getByText(/inputs have changed/),
    ).toBeInTheDocument();
    // Back to the inputs of the shown run: current again.
    await userEvent.type(drag, "{backspace}");
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
    await userEvent.type(drag, "5");
    mockFetch(200, RESPONSE); // a fresh response: a body can be read only once
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByRole("status")).toHaveTextContent(/Run complete/);
    expect(screen.queryByText(/inputs have changed/)).not.toBeInTheDocument();
  });

  it("does not hand the charts new layouts while the user types", async () => {
    mockFetch(200, RESPONSE);
    layouts.clear();
    render(<ProjectileLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    await screen.findByText("Analytical vs numerical");
    await userEvent.type(screen.getByLabelText(/^Mass/), "1");
    expect(layouts.size).toBeGreaterThan(0);
    for (const [title, seen] of layouts) {
      expect(new Set(seen).size, title).toBe(1);
    }
  });

  it("submits validated inputs and renders the comparison", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<ProjectileLab />);

    const mass = screen.getByLabelText(/^Mass/);
    await userEvent.clear(mass);
    await userEvent.type(mass, "2.5");
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));

    expect(await screen.findByText("Analytical vs numerical")).toBeInTheDocument();
    expect(screen.getByTestId("max-position-error")).toHaveTextContent("2.2e-11 m");
    expect(screen.getByText("The projectile is a point mass.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Trajectory/ })).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/projectile/simulate");
    const sent = JSON.parse(init.body);
    expect(sent.parameters.mass).toBe(2.5);
    expect(sent.solver.method).toBe("DOP853");
  });

  it("blocks submission and explains invalid input", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<ProjectileLab />);

    const speed = screen.getByLabelText(/^Initial speed/);
    await userEvent.clear(speed);
    await userEvent.type(speed, "-5");
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));

    expect(screen.getByText("Must be ≥ 0.001")).toBeInTheDocument();
    expect(speed).toHaveAttribute("aria-invalid", "true");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server's explanation when the API rejects a run", async () => {
    mockFetch(422, {
      detail: [{ loc: ["body", "parameters"], msg: "Value error, zero flight time" }],
    });
    render(<ProjectileLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run simulation" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("parameters: zero flight time");
  });
});
