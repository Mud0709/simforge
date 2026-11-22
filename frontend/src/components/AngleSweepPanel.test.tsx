import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { AngleSweepResponse, ProjectileParameters } from "@/lib/api/client";
import { AngleSweepPanel } from "./AngleSweepPanel";

// Each chart's traces and layout are recorded by title, so a test can read what would be drawn.
type Trace = { name?: string; x?: number[]; y?: number[]; mode?: string };
type Layout = { xaxis?: { title?: { text?: string } }; yaxis?: { title?: { text?: string } } };
const charts = new Map<string, { data: Trace[]; layout: Layout }>();
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title, data, layout }: { title: string; data: Trace[]; layout: Layout }) => {
    charts.set(title, { data, layout });
    return <div role="img" aria-label={title} />;
  },
}));

const PARAMS = {
  initial_speed: 20,
  launch_angle_deg: 45,
  launch_height: 0,
  mass: 1,
  drag_coefficient: 1,
  gravity: 9.80665,
} as ProjectileParameters;

const CHECKS = [
  {
    id: "energy_balance",
    label: "Energy balance",
    value: 1.3e-12,
    threshold: 1e-9,
    passed: true,
    kind: "numerical_diagnostic",
    note: "Energy balance note",
  },
  {
    id: "cost",
    label: "Cost",
    value: 70,
    threshold: null,
    passed: null,
    kind: "informational",
    note: "Cost note",
  },
];

const RESPONSE = {
  checks: CHECKS,
  angles_deg: [0, 45, 90],
  ranges: [0, 12.5, 0],
  flight_times: [0, 2.16, 2.5],
  max_heights: [0, 5.4, 9],
  best_angle_deg: 30.0774,
  best_range: 13.8929,
  vacuum_best_angle_deg: 45,
  vacuum_best_range: 40.7886,
  method_note: "Exact solution.",
  model: { id: "physics.projectile.angle_sweep" },
  metadata: { run_id: "0123abcd-0000-0000-0000-000000000000" },
  units: { angle: "deg", range: "m", flight_time: "s", max_height: "m" },
} as unknown as AngleSweepResponse;

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

describe("AngleSweepPanel", () => {
  it("sweeps with the current parameters and shows the best angle", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));

    expect(await screen.findByTestId("best-angle")).toHaveTextContent("30.08°");
    expect(screen.getByTestId("best-range")).toHaveTextContent("13.8929 m");
    expect(screen.getByTestId("vacuum-angle")).toHaveTextContent("45.00°");
    expect(screen.getByRole("img", { name: "Range against launch angle" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Download range against angle (CSV)" }),
    ).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/physics/projectile/angle-sweep");
    expect(JSON.parse(init.body).parameters).toEqual(PARAMS);
  });

  it("shows the shared ChecksTable and keeps the best-angle figures and the range chart", async () => {
    mockFetch(200, RESPONSE);
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByTestId("check-energy_balance")).toHaveTextContent("Pass");
    expect(screen.getByTestId("check-cost")).toHaveTextContent("Info");
    // Kept alongside: the exact-vs-vacuum table of the sweep.
    expect(screen.getByTestId("best-angle")).toHaveTextContent("30.08°");
    expect(screen.getByTestId("vacuum-angle")).toHaveTextContent("45.00°");
  });

  it("shows the server's explanation on failure", async () => {
    mockFetch(422, { detail: "n_angles: Input should be less than or equal to 361" });
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("less than or equal to 361");
  });

  // Roadmap 2.5, D13: the shared panel is generalised from angles to any swept variable. These
  // tests go through the public AngleSweepPanel only (its props and what it shows), so they
  // pass before and after the generalisation: what the angle sweep draws and says is unchanged.
  it("draws the analytical range curve and the best angle, over 0 to 90 degrees", async () => {
    mockFetch(200, RESPONSE);
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    await screen.findByTestId("best-angle");
    const { data, layout } = charts.get("Range against launch angle")!;
    // No vacuum curve for the linear-drag sweep: only the curve and the best-angle marker.
    expect(data.map((t) => t.name)).toEqual(["Range (analytical)", "Best angle"]);
    expect(data[0]!.x).toEqual([0, 45, 90]);
    expect(data[0]!.y).toEqual([0, 12.5, 0]);
    expect(data[1]!.x).toEqual([30.0774]);
    expect(data[1]!.y).toEqual([13.8929]);
    expect(data[1]!.mode).toBe("markers");
    expect(layout.xaxis?.title?.text).toBe("Launch angle (°)");
    expect(layout.yaxis?.title?.text).toBe("Range (m)");
  });

  it("labels the best angle 'with drag' only when there is drag, and has no angle-count field", async () => {
    mockFetch(200, RESPONSE);
    const withDrag = render(<AngleSweepPanel parameters={PARAMS} />);
    expect(screen.queryByLabelText(/Number of angles/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByText("Best angle (with drag)")).toBeInTheDocument();
    withDrag.unmount();

    mockFetch(200, RESPONSE);
    render(<AngleSweepPanel parameters={{ ...PARAMS, drag_coefficient: 0 }} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByText("Best angle")).toBeInTheDocument();
    expect(screen.queryByText("Best angle (with drag)")).not.toBeInTheDocument();
  });

  it("says 'Sweeping…' and disables the button while the server works", async () => {
    let finish!: (r: Response) => void;
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>((resolve) => (finish = resolve))),
    );
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByRole("button", { name: "Sweeping…" })).toBeDisabled();
    finish(
      new Response(JSON.stringify(RESPONSE), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    expect(await screen.findByTestId("best-angle")).toBeInTheDocument();
  });
});
