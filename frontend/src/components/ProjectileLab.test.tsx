import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { ProjectileResponse } from "@/lib/api/client";
import { ProjectileLab } from "./ProjectileLab";

// Plotly needs a real browser (canvas, SVG layout); charts are covered by the E2E test.
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
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

    expect(screen.getByText("Must be > 0")).toBeInTheDocument();
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
