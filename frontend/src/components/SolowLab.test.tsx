import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { SolowResponse } from "@/lib/api/client";
import { SolowLab } from "./SolowLab";

// Plotly needs a real browser; charts are covered by the E2E test.
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
}));

const path = (s: number[]) => ({
  savings_rate: s,
  capital: [1, 1.5, 2],
  output: [1, 1.1, 1.2],
  consumption: [0.8, 0.77, 0.84],
  investment: [0.2, 0.33, 0.36],
  output_per_worker_index: [100, 103, 106],
  output_per_worker_growth: [0.03, 0.028],
});
const steady = (s: number, k: number) => ({
  savings_rate: s,
  capital: k,
  output: k ** 0.3,
  consumption: (1 - s) * k ** 0.3,
  capital_output_ratio: s / 0.0802,
});
const RESPONSE = {
  model: { id: "economy.solow", version: "1.0.0", name: "Solow", description: "" },
  parameters: { capital_share: 0.3 },
  policy: { new_savings_rate: 0.3, policy_year: 1 },
  horizon_years: 2,
  units: {},
  assumptions: [{ id: "cobb_douglas", statement: "Production is Cobb-Douglas." }],
  years: [0, 1, 2],
  baseline: path([0.2, 0.2, 0.2]),
  scenario: path([0.2, 0.3, 0.3]),
  baseline_steady_state: steady(0.2, 3.689237466703935),
  scenario_steady_state: steady(0.3, 6.584086866307975),
  golden_rule: steady(0.3, 6.584086866307975),
  convergence: {
    effective_depreciation: 0.0802,
    growth_factor: 1.0302,
    rho: 0.9455,
    one_minus_rho: 0.0545,
    half_life_years: 12.3698,
  },
  initial_capital: 1,
  checks: [
    {
      id: "identical_before_policy",
      label: "Baseline = scenario before the change",
      value: 0,
      threshold: 0,
      passed: true,
      kind: "exact_identity",
      note: "",
    },
    {
      id: "distance_to_new_steady_state",
      label: "Final distance from k*(s1)",
      value: 0.0068,
      threshold: null,
      passed: null,
      kind: "informational",
      note: "",
    },
  ],
  method_note: "Exact recurrence.",
  metadata: {
    run_id: "abc",
    created_at: "2026-01-01T00:00:00Z",
    input_hash: "f".repeat(64),
    simforge_version: "0.1.0",
    python_version: "3.12",
    numpy_version: "2",
    scipy_version: "1",
    platform: "test",
    elapsed_ms: 1,
    experiment_saved: true,
  },
} as unknown as SolowResponse;

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

describe("SolowLab", () => {
  it("lays out the five workspace sections before any run", () => {
    render(<SolowLab />);
    for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
      expect(screen.getByRole("region", { name })).toBeInTheDocument();
    }
  });

  it("sends fractions exactly as typed and renders every section", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<SolowLab />);

    const s1 = screen.getByLabelText(/^New savings rate/);
    await userEvent.clear(s1);
    await userEvent.type(s1, "0.35");
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));

    expect(await screen.findByTestId("steady-state-baseline")).toHaveTextContent("3.68924");
    expect(screen.getByTestId("golden-rule-rate")).toHaveTextContent("0.3");
    expect(screen.getByTestId("half-life")).toHaveTextContent("12.37 years");
    expect(
      screen.getByRole("button", { name: "Download baseline and scenario paths (CSV)" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Production is Cobb-Douglas.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Capital per effective worker/ })).toBeInTheDocument();
    const check = screen.getByTestId("check-identical_before_policy");
    expect(within(check).getByText("Pass")).toBeInTheDocument();
    expect(within(check).getByText("Exact identity")).toBeInTheDocument();

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/v1/economy/solow/simulate");
    const sent = JSON.parse(init.body);
    expect(sent.policy).toEqual({ new_savings_rate: 0.35, policy_year: 20 });
    expect(sent.parameters.capital_share).toBe(0.3);
    expect(sent.parameters.technology_growth).toBe(0.02);
    expect(sent.horizon_years).toBe(100);
  });

  it("rejects fractional years and a policy year beyond the horizon", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<SolowLab />);
    const horizon = screen.getByLabelText(/^Horizon/);
    await userEvent.clear(horizon);
    await userEvent.type(horizon, "10.5");
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    expect(screen.getByText("Must be a whole number")).toBeInTheDocument();

    await userEvent.clear(horizon);
    await userEvent.type(horizon, "20");
    expect(screen.getByText("Must be below the horizon")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("refuses rates with no useful steady state before calling the server", async () => {
    const fetchMock = mockFetch(200, RESPONSE);
    render(<SolowLab />);
    const set = async (label: RegExp, v: string) => {
      const input = screen.getByLabelText(label);
      await userEvent.clear(input);
      await userEvent.type(input, v);
    };
    // n + g + ng + delta = -0.05 + 0 + 0 + 0.05 = 0: every field is fine on its own.
    await set(/^Population growth/, "-0.05");
    await set(/^Technology growth/, "0");
    await set(/^Depreciation/, "0.05");
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    expect(screen.getByText(/n \+ g \+ ng \+ δ = 0 is below 0\.001/)).toBeInTheDocument();
    // 5e-4: positive, but still below the bound.
    await set(/^Depreciation/, "0.0505");
    expect(screen.getByText(/= 0\.0005 is below 0\.001/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();

    // Exactly at the bound (sum 0.001, a few ulps below in floating point) is accepted.
    await set(/^Depreciation/, "0.051");
    expect(screen.queryByText(/is below 0\.001/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("writes a failed count check as a whole number", async () => {
    const failing = {
      ...RESPONSE,
      checks: [{ ...RESPONSE.checks[0]!, value: 3, passed: false }],
    };
    mockFetch(200, failing);
    render(<SolowLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    const row = await screen.findByTestId("check-identical_before_policy");
    expect(within(row).getByText("3")).toBeInTheDocument();
    expect(within(row).queryByText("3e0")).not.toBeInTheDocument();
  });

  it("marks the results as out of date when an input changes or a re-run fails", async () => {
    mockFetch(200, RESPONSE);
    render(<SolowLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    await screen.findByTestId("steady-state-baseline");
    const s1 = screen.getByLabelText(/^New savings rate/);
    await userEvent.clear(s1);
    await userEvent.type(s1, "0.5");
    mockFetch(422, { detail: [{ loc: ["body"], msg: "refused" }] });
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    await screen.findByRole("alert");
    expect(
      within(screen.getByRole("region", { name: "Results" })).getByText(/inputs have changed/),
    ).toBeInTheDocument();
  });

  it("shows the server's explanation when the API rejects a run", async () => {
    mockFetch(422, {
      detail: [
        { loc: ["body", "parameters"], msg: "Value error, no steady state for these rates" },
      ],
    });
    render(<SolowLab />);
    await userEvent.click(screen.getByRole("button", { name: "Run model" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "parameters: no steady state for these rates",
    );
  });
});
