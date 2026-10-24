import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { IntegratorStudyResponse } from "@/lib/api/client";
import { IntegratorLab } from "./IntegratorLab";

vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
}));

const run = (h: number, err: number, inFit: boolean) => ({
  dt_requested: h,
  h,
  n_steps: Math.round(2 / h),
  kh: h,
  amplification_factor: 1 - h,
  stability: "stable",
  diverged: false,
  n_completed: Math.round(2 / h),
  max_position_error: err,
  max_velocity_error: err,
  final_position_error: err,
  final_velocity_error: err,
  position_roundoff_floor: 1e-12,
  velocity_roundoff_floor: 1e-12,
  in_position_fit: inFit,
  in_velocity_fit: inFit,
  exclusion_reason: inFit ? null : "not asymptotic: h/T = 0.1 > 1/20",
});

const RESPONSE = {
  model: { id: "physics.projectile.integrators", version: "1.0.0", name: "Study", description: "" },
  parameters: {},
  dt_values: [0.2, 0.1, 0.05, 0.025],
  methods: ["euler"],
  units: {},
  assumptions: [{ id: "fixed_horizon", statement: "Fixed horizon." }],
  horizon: 2.16,
  k: 1,
  position_scale: 10,
  velocity_scale: 20,
  fit_rule: {
    max_kh: 0.2,
    max_h_over_horizon: 0.05,
    roundoff_safety_factor: 100,
    min_points: 3,
    description: "Rule text.",
  },
  results: [
    {
      method: "euler",
      name: "Forward Euler",
      theoretical_order: 1,
      stability_limit_kh: 2,
      runs: [
        run(0.2, 1.1, false),
        run(0.1, 0.52, true),
        run(0.05, 0.26, true),
        run(0.025, 0.13, true),
      ],
      position_local_orders: [1.07, 1.03, 1.01],
      velocity_local_orders: [1.07, 1.03, 1.01],
      position_fit: {
        order: 1.0089,
        theoretical_order: 1,
        r_squared: 0.99999,
        n_points: 3,
        h_min: 0.025,
        h_max: 0.1,
      },
      velocity_fit: {
        order: 1.0089,
        theoretical_order: 1,
        r_squared: 0.99999,
        n_points: 3,
        h_min: 0.025,
        h_max: 0.1,
      },
      position_reference: { order: 1, h: [0.025, 0.1], error: [0.13, 0.52] },
      velocity_reference: { order: 1, h: [0.025, 0.1], error: [0.13, 0.52] },
      fit_note: null,
      trajectory: { h: 0.1, x: [0, 1], y: [0, 1] },
    },
  ],
  exact_trajectory: { x: [0, 1], y: [0, 1] },
  metadata: {
    run_id: "abc",
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
} as unknown as IntegratorStudyResponse;

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

afterEach(() => vi.unstubAllGlobals());

describe("IntegratorLab", () => {
  it("puts each part of the study in its workspace section", async () => {
    mockFetch(200, RESPONSE);
    render(<IntegratorLab />);
    const region = (name: string) => screen.getByRole("region", { name });
    expect(within(region("Parameters")).getByLabelText(/^Time steps/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));

    await screen.findByTestId("order-euler");
    expect(within(region("Results")).getByTestId("order-euler")).toBeInTheDocument();
    expect(
      within(region("Results")).getByRole("button", { name: "Download trajectories (CSV)" }),
    ).toBeInTheDocument();
    expect(
      within(region("Visualisation")).getByRole("img", {
        name: /maximum position error against time step/,
      }),
    ).toBeInTheDocument();
    const validation = within(region("Validation"));
    expect(validation.getByText(/Rule text\./)).toBeInTheDocument();
    expect(validation.getAllByText(/All runs:/).length).toBeGreaterThan(0);
    expect(validation.getByText(RESPONSE.metadata.run_id)).toBeInTheDocument();
    expect(
      within(region("Visualisation")).getByRole("img", { name: /^Trajectories from each method/ }),
    ).toBeInTheDocument();
    expect(within(region("Results")).queryByRole("img")).not.toBeInTheDocument();
    expect(within(region("Visualisation")).queryByTestId("order-euler")).not.toBeInTheDocument();
    expect(within(region("Assumptions")).getByText("Fixed horizon.")).toBeInTheDocument();
  });

  it("marks the study as out of date when the time steps change", async () => {
    mockFetch(200, RESPONSE);
    render(<IntegratorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));
    await screen.findByTestId("order-euler");
    await userEvent.type(screen.getByLabelText(/^Time steps/), ", 0.5");
    expect(
      within(screen.getByRole("region", { name: "Results" })).getByText(/inputs have changed/),
    ).toBeInTheDocument();
  });

  it("sends the study request and renders orders and plots", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<IntegratorLab />);
    await userEvent.click(screen.getByRole("checkbox", { name: /Velocity Verlet/ }));
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));

    const row = await screen.findByTestId("order-euler");
    expect(row).toHaveTextContent("1.009");
    expect(
      screen.getByRole("img", { name: /maximum position error against time step/ }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Rule text\./)).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/projectile/integrators");
    const sent = JSON.parse(init.body);
    expect(sent.methods).toEqual(["euler", "rk4"]);
    expect(sent.parameters.drag_coefficient).toBe(1);
    expect(sent.dt_values).toHaveLength(8);
  });

  it("refuses zero drag, bad steps and no methods without calling the API", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<IntegratorLab />);
    const drag = screen.getByLabelText(/^Drag coefficient/);
    await userEvent.clear(drag);
    await userEvent.type(drag, "0");
    const steps = screen.getByLabelText(/^Time steps/);
    await userEvent.clear(steps);
    await userEvent.type(steps, "0.1, 0.1");
    for (const box of screen.getAllByRole("checkbox")) await userEvent.click(box);
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));

    expect(screen.getByText(/Must be > 0 for this study/)).toBeInTheDocument();
    expect(screen.getByText("Remove duplicate time steps")).toBeInTheDocument();
    expect(screen.getByText("Select at least one method")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the server's explanation when a study is refused", async () => {
    mockFetch(422, { detail: "dt = 1e-06 s needs 2160642 steps; the limit is 50000 per run." });
    render(<IntegratorLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run study" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the limit is 50000 per run");
  });
});
