/**
 * Reopening a saved run: a lab page opened with ?run=<id> fills its form with that run's
 * stored inputs and runs nothing until the user presses Run.
 */
import { render, screen, within } from "@testing-library/react";
import { vi } from "vitest";

import { reopenLink } from "@/lib/runs/pages";

import { ExperimentLog } from "./ExperimentLog";
import { ProjectileLab } from "./ProjectileLab";
import { QuadraticDragLab } from "./QuadraticDragLab";
import { QuantLab } from "./QuantLab";
import { SolowLab } from "./SolowLab";

vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
}));

function record(model_id: string, inputs: unknown, summary: unknown = {}) {
  return {
    run_id: "0123456789abcdef",
    model_id,
    model_version: "1.0.0",
    created_at: "2026-10-23T10:00:00+00:00",
    input_hash: "a".repeat(64),
    inputs,
    summary,
    environment: {},
    record_version: 2,
    output_digest: "b".repeat(64),
    replay_of: null,
    lab: model_id.split(".")[0],
    headline: "h",
  };
}

/** GET /experiments/<id> returns `run`; every other request is recorded and answered []. */
function mockApi(run: unknown) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      const body = /\/experiments\/[^/?]+$/.test(url) ? run : [];
      return Promise.resolve(
        new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }),
      );
    }),
  );
  return calls;
}

function openPage(path: string) {
  window.history.pushState({}, "", path);
}

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

const SOLOW_INPUTS = {
  parameters: {
    capital_share: 0.35,
    savings_rate: 0.25,
    depreciation: 0.04,
    population_growth: 0.015,
    technology_growth: 0.02,
    initial_capital_ratio: 0.7,
  },
  policy: { new_savings_rate: 0.35, policy_year: 12 },
  horizon_years: 80,
};

describe("reopening a run", () => {
  it("fills the Solow form from the stored inputs and runs nothing", async () => {
    const calls = mockApi(record("economy.solow", SOLOW_INPUTS));
    openPage("/economy/solow?run=0123456789abcdef");
    render(<SolowLab />);
    expect(await screen.findByText(/Loaded the inputs of run 01234567/)).toBeInTheDocument();
    expect(screen.getByLabelText(/^Capital share/)).toHaveValue("0.35");
    expect(screen.getByLabelText(/^Policy year/)).toHaveValue("12");
    expect(screen.getByLabelText(/^Horizon/)).toHaveValue("80");
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);
  });

  it("fills the projectile form, including the solver", async () => {
    mockApi(
      record("physics.projectile", {
        parameters: {
          initial_speed: 12,
          launch_angle_deg: 30,
          launch_height: 0,
          mass: 2,
          drag_coefficient: 0.5,
          gravity: 9.80665,
        },
        solver: { method: "Radau", rtol: 1e-8, atol: 1e-9 },
        n_samples: 400,
      }),
    );
    openPage("/physics/projectile?run=0123456789abcdef");
    render(<ProjectileLab />);
    await screen.findByText(/Loaded the inputs of run/);
    expect(screen.getByLabelText(/^Initial speed/)).toHaveValue("12");
    expect(screen.getByLabelText(/^Drag coefficient/)).toHaveValue("0.5");
    expect(screen.getByLabelText("Method")).toHaveValue("Radau");
  });

  it("fills the quadratic-drag form, including the solver, on its own page", async () => {
    const calls = mockApi(
      record("physics.projectile.quadratic_drag", {
        parameters: {
          initial_speed: 14,
          launch_angle_deg: 90,
          launch_height: 3,
          mass: 0.5,
          drag_constant: 0.002,
          gravity: 9.81,
        },
        solver: { method: "RK45", rtol: 1e-8, atol: 1e-9 },
        n_samples: 400,
      }),
    );
    expect(reopenLink("physics.projectile.quadratic_drag", "0123456789abcdef")).toBe(
      "/physics/projectile/quadratic-drag?run=0123456789abcdef",
    );
    openPage("/physics/projectile/quadratic-drag?run=0123456789abcdef");
    render(<QuadraticDragLab />);
    await screen.findByText(/Loaded the inputs of run 01234567/);
    expect(screen.getByLabelText(/^Initial speed/)).toHaveValue("14");
    expect(screen.getByLabelText(/^Launch angle/)).toHaveValue("90");
    expect(screen.getByLabelText(/^Drag constant c/)).toHaveValue("0.002");
    expect(screen.getByLabelText(/^Gravity/)).toHaveValue("9.81");
    expect(screen.getByLabelText("Method")).toHaveValue("RK45");
    expect(screen.getByLabelText(/^Relative tolerance/)).toHaveValue("1e-8");
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);
  });

  it("refuses a linear-drag run on the quadratic-drag page", async () => {
    mockApi(record("physics.projectile", { parameters: { drag_coefficient: 0.5 } }));
    openPage("/physics/projectile/quadratic-drag?run=0123456789abcdef");
    render(<QuadraticDragLab />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/physics\.projectile run/);
    expect(screen.getByLabelText(/^Drag constant c/)).toHaveValue("0.01");
  });

  it("fills the quadratic-drag form from a quadratic sweep, keeping the launch angle", async () => {
    const calls = mockApi(
      record("physics.projectile.quadratic_angle_sweep", {
        // As stored by the backend: no launch angle (a sweep varies it).
        parameters: {
          initial_speed: 16.3,
          launch_height: 2.3,
          mass: 0.5,
          drag_constant: 0.0123,
          gravity: 9.81,
        },
        solver: { method: "Radau", rtol: 1e-7, atol: 1e-8 },
        n_angles: 11,
      }),
    );
    openPage("/physics/projectile/quadratic-drag?run=0123456789abcdef");
    render(<QuadraticDragLab />);
    await screen.findByText(/Run the simulation, then sweep the launch angle/);
    expect(screen.getByLabelText(/^Initial speed/)).toHaveValue("16.3");
    expect(screen.getByLabelText(/^Drag constant c/)).toHaveValue("0.0123");
    // The schema's default launch angle, 45°, stays: the sweep has none to restore.
    expect(screen.getByLabelText(/^Launch angle/)).toHaveValue("45");
    expect(screen.getByLabelText("Method")).toHaveValue("Radau");
    expect(calls.filter((c) => c.startsWith("POST"))).toEqual([]);
  });

  it("refuses the other drag law's sweep on each projectile page", async () => {
    mockApi(record("physics.projectile.angle_sweep", { parameters: {}, n_angles: 91 }));
    openPage("/physics/projectile/quadratic-drag?run=0123456789abcdef");
    const { unmount } = render(<QuadraticDragLab />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /physics\.projectile\.angle_sweep run/,
    );
    unmount();

    mockApi(record("physics.projectile.quadratic_angle_sweep", { parameters: {}, n_angles: 91 }));
    openPage("/physics/projectile?run=0123456789abcdef");
    render(<ProjectileLab />);
    expect(await screen.findByRole("alert")).toHaveTextContent(
      /physics\.projectile\.quadratic_angle_sweep run/,
    );
  });

  it("asks for the file again when the run profiled an upload", async () => {
    mockApi(
      record(
        "quant.dataset_profile",
        {
          dataset: { sha256: "c".repeat(64), byte_size: 42 },
          options: { delimiter: "semicolon", missing_markers: ["-", "NA"], column_types: [] },
        },
        { source: "upload", sample_id: null },
      ),
    );
    openPage("/quant/datasets?run=0123456789abcdef");
    render(<QuantLab />);
    expect(await screen.findByText(/choose the same file again/)).toBeInTheDocument();
    expect(screen.getByLabelText("Upload a CSV file")).toBeChecked();
    expect(screen.getByLabelText("Delimiter")).toHaveValue("semicolon");
    expect(screen.getByLabelText("Missing-value markers")).toHaveValue("-, NA");
  });

  it("refuses a run from another model", async () => {
    mockApi(record("economy.solow", SOLOW_INPUTS));
    openPage("/physics/projectile?run=0123456789abcdef");
    render(<ProjectileLab />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/economy\.solow/);
    expect(screen.getByLabelText(/^Initial speed/)).toHaveValue("20");
  });

  it("links each run in the log to its page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify([record("economy.solow", SOLOW_INPUTS)]), {
            headers: { "Content-Type": "application/json" },
          }),
        ),
      ),
    );
    render(<ExperimentLog />);
    const row = await screen.findByRole("row", { name: /economy\.solow/ });
    expect(within(row).getByRole("link", { name: "Open" })).toHaveAttribute(
      "href",
      "/economy/solow?run=0123456789abcdef",
    );
  });
});
