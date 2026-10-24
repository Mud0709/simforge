/**
 * The comparison table of a reference run (roadmap 1.6, D8 option b), as the reader sees it:
 * changed inputs, then each headline summary value with its absolute and relative change.
 * No "within tolerance" verdicts: replay tolerances measure numerical reproducibility, not
 * whether a change between two scenarios matters. Expected text is worked out by hand.
 */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { ModelResponse } from "@/lib/api/client";
import { AngleSweepPanel } from "./AngleSweepPanel";
import { ComparisonTable } from "./ComparisonTable";
import { QuantLab } from "./QuantLab";
import { SolowLab } from "./SolowLab";
import PROFILE from "./fixtures/messySurveyProfile.json";

const plotly = vi.hoisted(() => ({ react: vi.fn(), purge: vi.fn() }));
vi.mock("plotly.js-dist-min", () => ({ default: plotly }));

afterEach(() => {
  vi.unstubAllGlobals();
  window.history.pushState({}, "", "/");
});

function solow(o: {
  runId: string;
  k0?: number;
  golden?: number;
  halfLife?: number;
  newSavings?: number;
}) {
  const path = (capital: number[]) => ({
    savings_rate: [0.2, 0.3, 0.3],
    capital,
    output: [1, 1.1, 1.2],
    consumption: [0.5, 0.6, 0.7],
    investment: [0.2, 0.33, 0.36],
    output_per_worker_index: [100, 103, 106],
    output_per_worker_growth: [0.03, 0.028],
  });
  const steady = { savings_rate: 0.2, capital: 3, output: 1.4, consumption: 1.1 };
  return {
    model: { id: "economy.solow", version: "1.0.0", name: "Solow growth model" },
    parameters: { capital_share: 0.3 },
    policy: { new_savings_rate: o.newSavings ?? 0.3, policy_year: 1 },
    horizon_years: 2,
    units: { years: "year" },
    assumptions: [],
    years: [0, 1, 2],
    baseline: path([2, 2.5, 3]),
    scenario: path([2, 2.7, 3.4]),
    baseline_steady_state: { ...steady, capital: o.k0 ?? 2, capital_output_ratio: 2.5 },
    scenario_steady_state: { ...steady, capital_output_ratio: 3.7 },
    golden_rule: { ...steady, savings_rate: o.golden ?? 0.3, capital_output_ratio: 3.7 },
    convergence: {
      effective_depreciation: 0.08,
      growth_factor: 1.03,
      rho: 0.95,
      one_minus_rho: 0.05,
      half_life_years: o.halfLife ?? 12,
    },
    initial_capital: 1,
    checks: [],
    method_note: "Exact recurrence.",
    metadata: { run_id: o.runId, experiment_saved: true, output_digest: "e".repeat(64) },
  };
}
const as = (r: unknown) => r as ModelResponse;

/** The cells of the summary row for `field`, as text. */
function summaryRow(field: string): string[] {
  const table = screen.getByRole("table", { name: /Summary: reference run and this run/ });
  const row = within(table)
    .getAllByRole("row")
    .find((r) => within(r).queryByText(field, { selector: "code" }));
  if (!row) throw new Error(`no row for ${field}`);
  return within(row)
    .getAllByRole("cell")
    .map((c) => c.textContent ?? "");
}

describe("ComparisonTable", () => {
  it("shows absolute and relative changes, signed, and '—' where the reference is 0", () => {
    render(
      <ComparisonTable
        reference={as(solow({ runId: "a", k0: 2, golden: 0, halfLife: -4 }))}
        current={as(solow({ runId: "b", k0: 3, golden: 0.3, halfLife: -2 }))}
      />,
    );
    // field, reference, current, absolute change, relative change
    expect(summaryRow("baseline_steady_state_capital")).toEqual(["2", "3", "+1", "+50%"]);
    expect(summaryRow("half_life_years")).toEqual(["-4", "-2", "+2", "+50%"]);
    expect(summaryRow("golden_rule_savings_rate")).toEqual(["0", "0.3", "+0.3", "—"]);
    expect(summaryRow("final_capital")).toEqual(["3.4", "3.4", "0", "0%"]);
    expect(screen.getByText(/relative change is undefined/i)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/Infinity|NaN|tolerance/i);
  });

  it("never shows a non-finite change: an overflowing ratio is '—', not '+—' or Infinity", () => {
    // 1 / 5e-324 overflows to Infinity, so the relative change cannot be shown as a number.
    render(
      <ComparisonTable
        reference={as(solow({ runId: "a", golden: 5e-324 }))}
        current={as(solow({ runId: "b", golden: 1 }))}
      />,
    );
    expect(summaryRow("golden_rule_savings_rate")).toEqual(["4.94066e-324", "1", "+1", "—"]);
    expect(document.body.textContent).not.toMatch(/Infinity|NaN|\+—/);
  });

  it("lists only the inputs that differ", () => {
    render(
      <ComparisonTable
        reference={as(solow({ runId: "a", newSavings: 0.3 }))}
        current={as(solow({ runId: "b", newSavings: 0.35 }))}
      />,
    );
    const inputs = screen.getByRole("table", { name: /Inputs that differ/ });
    const rows = within(inputs).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(1);
    expect(rows[0]).toHaveTextContent("policy.new_savings_rate");
    expect(
      within(rows[0]!)
        .getAllByRole("cell")
        .map((c) => c.textContent),
    ).toEqual(["0.3", "0.35"]);
  });

  it("says so when no input differs, and notes when every number is exactly equal", () => {
    render(
      <ComparisonTable reference={as(solow({ runId: "a" }))} current={as(solow({ runId: "b" }))} />,
    );
    expect(screen.getByText(/No input differs/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(/every numeric summary value is exactly/i);
  });

  it("shows non-numeric values as equal or changed", () => {
    const other = {
      ...PROFILE,
      dataset: { ...PROFILE.dataset, sample_id: "lab_measurements" },
      metadata: { ...PROFILE.metadata, run_id: "other-run" },
    };
    render(<ComparisonTable reference={as(PROFILE)} current={as(other)} />);
    expect(summaryRow("sample_id")).toEqual(["messy_survey", "lab_measurements", "changed", ""]);
    expect(summaryRow("source")).toEqual(["sample", "sample", "equal", ""]);
  });

  it("renders nothing for two different models, or for the reference itself", () => {
    const { container, rerender } = render(
      <ComparisonTable reference={as(PROFILE)} current={as(solow({ runId: "b" }))} />,
    );
    expect(container).toBeEmptyDOMElement();
    const same = as(solow({ runId: "a" }));
    rerender(<ComparisonTable reference={same} current={same} />);
    expect(container).toBeEmptyDOMElement();
  });
});

// ---------- wired into the labs ----------

function mockApi(routes: Record<string, unknown>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      const body = routes[`${init?.method ?? "GET"} ${url}`];
      return Promise.resolve(
        new Response(JSON.stringify(body ?? { detail: "unexpected" }), {
          status: body === undefined ? 404 : 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }),
  );
}

it("the Solow lab shows the comparison under a ?ref= reference", async () => {
  mockApi({
    "POST /api/v1/experiments/ref-solow/outputs": {
      original_run_id: "ref-solow",
      digest_match: true,
      response: solow({ runId: "recomputed", k0: 2, newSavings: 0.3 }),
    },
    "POST /api/v1/economy/solow/simulate": solow({ runId: "now", k0: 3, newSavings: 0.35 }),
  });
  window.history.pushState({}, "", "/economy/solow?ref=ref-solow");
  render(<SolowLab />);
  await userEvent.click(screen.getByRole("button", { name: "Run model" }));
  const inputs = await screen.findByRole("table", { name: /Inputs that differ/ });
  expect(inputs).toHaveTextContent("policy.new_savings_rate");
  expect(summaryRow("baseline_steady_state_capital")).toEqual(["2", "3", "+1", "+50%"]);
});

it("the dataset profile is compared by its summary: same file twice, every count equal", async () => {
  const saved = { ...PROFILE, metadata: { ...PROFILE.metadata, experiment_saved: true } };
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const body = url.endsWith("/samples")
        ? [{ id: "messy_survey", title: "Survey", description: "" }]
        : { ...saved, metadata: { ...saved.metadata, run_id: `profile-${++n}` } };
      return Promise.resolve(
        new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }),
      );
    }),
  );
  window.history.pushState({}, "", "/quant/datasets");
  render(<QuantLab />);
  await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
  await userEvent.click(await screen.findByRole("button", { name: "Pin as reference run" }));
  expect(screen.queryByRole("table", { name: /Summary: reference run/ })).toBeNull();
  await userEvent.click(screen.getByRole("button", { name: "Profile again" }));

  expect(await screen.findByText(/No input differs/)).toBeInTheDocument();
  expect(summaryRow("mixed_columns")).toEqual(["2", "2", "0", "0%"]);
  expect(screen.getByText(/every numeric summary value is exactly/i)).toBeInTheDocument();
});

it("an angle sweep is compared with a reference sweep beside the sweep itself", async () => {
  const sweep = (runId: string, best: number) => ({
    model: { id: "physics.projectile.angle_sweep", version: "1.0.0", name: "Sweep" },
    parameters: { initial_speed: 20, launch_angle_deg: 45, mass: 1 },
    units: { angle: "deg", range: "m" },
    angles_deg: [0, 45, 90],
    ranges: [0, best, 0],
    flight_times: [0, 1, 0],
    max_heights: [0, 1, 0],
    best_angle_deg: 40,
    best_range: best,
    vacuum_best_angle_deg: 45,
    vacuum_best_range: 40.79,
    method_note: "Exact.",
    metadata: { run_id: runId, experiment_saved: true },
  });
  mockApi({ "POST /api/v1/physics/projectile/angle-sweep": sweep("now", 12) });
  const reference = as(sweep("ref", 8));
  render(
    <AngleSweepPanel
      parameters={sweep("now", 12).parameters as never}
      referenceRun={{
        reference: {
          status: "ready",
          runId: "ref",
          response: reference,
          provenance: { kind: "session" },
        },
        response: reference,
        pin: vi.fn(),
        unpin: vi.fn(),
      }}
    />,
  );
  await userEvent.click(screen.getByRole("button", { name: "Sweep launch angle" }));
  // 8 -> 12 m: +4 m, and +4/8 = +50%.
  expect(await screen.findByText(/No input differs/)).toBeInTheDocument();
  expect(summaryRow("best_range")).toEqual(["8", "12", "+4", "+50%"]);
  expect(summaryRow("best_angle_deg")).toEqual(["40", "40", "0", "0%"]);
});
