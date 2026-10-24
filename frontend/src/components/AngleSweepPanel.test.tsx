import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { AngleSweepResponse, ProjectileParameters } from "@/lib/api/client";
import { AngleSweepPanel } from "./AngleSweepPanel";

vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
}));

const PARAMS = {
  initial_speed: 20,
  launch_angle_deg: 45,
  launch_height: 0,
  mass: 1,
  drag_coefficient: 1,
  gravity: 9.80665,
} as ProjectileParameters;

const RESPONSE = {
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

afterEach(() => vi.unstubAllGlobals());

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

  it("shows the server's explanation on failure", async () => {
    mockFetch(422, { detail: "n_angles: Input should be less than or equal to 361" });
    render(<AngleSweepPanel parameters={PARAMS} />);
    await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("less than or equal to 361");
  });
});
