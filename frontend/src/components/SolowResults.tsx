"use client";

import type { Data, Layout } from "plotly.js";
import { memo, useMemo } from "react";

import type { SolowResponse } from "@/lib/api/client";
import { formatSig } from "@/lib/format";
import { AssumptionsList } from "./AssumptionsList";
import { ChecksTable } from "./ChecksTable";
import { CsvDownloads } from "./CsvDownloads";
import { PlotlyChart } from "./PlotlyChart";

const BASELINE = "#64748b";
const SCENARIO = "#ea580c";
const REFERENCE = "#2563eb";

type Props = { result: SolowResponse };

/** Fields with a default are optional in the generated request types, but the server
 *  always returns them. Fail loudly rather than guess if one is ever missing. */
function present<T>(value: T | undefined, name: string): T {
  if (value === undefined) throw new Error(`Solow response is missing ${name}`);
  return value;
}

/** A horizontal dashed reference line spanning the whole x range. */
function hline(y: number, name: string, years: number[], color: string): Data {
  return {
    x: [years[0] ?? 0, years[years.length - 1] ?? 0],
    y: [y, y],
    name,
    mode: "lines",
    line: { color, dash: "dash", width: 1.5 },
  };
}

function policyLine(year: number): Partial<Layout> {
  return {
    shapes: [
      {
        type: "line",
        x0: year,
        x1: year,
        yref: "paper",
        y0: 0,
        y1: 1,
        line: { color: SCENARIO, dash: "dot", width: 1 },
      },
    ],
  };
}

function SolowChartsView({ result }: Props) {
  const { years, baseline, scenario, policy } = result;

  const capital = useMemo<Data[]>(
    () => [
      { x: years, y: baseline.capital, name: "Baseline", mode: "lines", line: { color: BASELINE } },
      { x: years, y: scenario.capital, name: "Scenario", mode: "lines", line: { color: SCENARIO } },
      hline(result.baseline_steady_state.capital, "k*(s₀)", years, BASELINE),
      hline(result.scenario_steady_state.capital, "k*(s₁)", years, SCENARIO),
    ],
    [result, years, baseline, scenario],
  );
  const consumption = useMemo<Data[]>(
    () => [
      {
        x: years,
        y: baseline.consumption,
        name: "Baseline",
        mode: "lines",
        line: { color: BASELINE },
      },
      {
        x: years,
        y: scenario.consumption,
        name: "Scenario",
        mode: "lines",
        line: { color: SCENARIO },
      },
      hline(result.golden_rule.consumption, "Golden-rule c*", years, REFERENCE),
    ],
    [result, years, baseline, scenario],
  );
  const perWorker = useMemo<Data[]>(
    () => [
      {
        x: years,
        y: baseline.output_per_worker_index,
        name: "Baseline",
        mode: "lines",
        line: { color: BASELINE },
      },
      {
        x: years,
        y: scenario.output_per_worker_index,
        name: "Scenario",
        mode: "lines",
        line: { color: SCENARIO },
      },
    ],
    [years, baseline, scenario],
  );

  const shared = policyLine(present(policy.policy_year, "policy_year"));
  const xaxis = { title: { text: "Year" } };
  return (
    <>
      <div className="chart-grid">
        <PlotlyChart
          title="Capital per effective worker over time"
          data={capital}
          height={300}
          layout={{ ...shared, xaxis, yaxis: { title: { text: "k (per effective worker)" } } }}
        />
        <PlotlyChart
          title="Consumption per effective worker over time"
          data={consumption}
          height={300}
          layout={{ ...shared, xaxis, yaxis: { title: { text: "c (per effective worker)" } } }}
        />
        <PlotlyChart
          title="Output per actual worker, index"
          data={perWorker}
          height={300}
          layout={{
            ...shared,
            xaxis,
            yaxis: { title: { text: "Y/L (year 0 = 100, log scale)" }, type: "log" },
          }}
        />
      </div>
      <p className="note">
        Dotted vertical line: the policy year. Per effective worker, the economy settles at a steady
        state; per actual worker, output keeps growing at the technology growth rate g, so the index
        uses a log scale, on which constant growth is a straight line.
      </p>
    </>
  );
}

function goldenRuleSentence(result: SolowResponse): string {
  const alpha = result.golden_rule.savings_rate;
  const s1 = present(result.policy.new_savings_rate, "new_savings_rate");
  const c0 = result.baseline_steady_state.consumption;
  const c1 = result.scenario_steady_state.consumption;
  const change = c1 > c0 ? "raises" : c1 < c0 ? "lowers" : "leaves unchanged";
  const position =
    s1 === alpha
      ? "equal to the golden-rule rate"
      : s1 < alpha
        ? "below the golden-rule rate"
        : "above the golden-rule rate, so the economy saves more than maximises long-run consumption";
  return (
    `The new savings rate ${s1} is ${position} (α = ${alpha}). Moving from s₀ to s₁ ${change} ` +
    "steady-state consumption per effective worker."
  );
}

export function SolowSummary({ result }: Props) {
  const { baseline_steady_state: b, scenario_steady_state: s, golden_rule: gr } = result;
  const { convergence: conv, scenario, policy, horizon_years: h } = result;
  const tc = present(policy.policy_year, "policy_year");
  const rows = [0, tc, tc + 1, h].filter((t, i, all) => t <= h && all.indexOf(t) === i);
  return (
    <>
      <dl className="stats">
        <div>
          <dt>Steady state k*(s₀)</dt>
          <dd data-testid="steady-state-baseline">{formatSig(b.capital)}</dd>
        </div>
        <div>
          <dt>Steady state k*(s₁)</dt>
          <dd data-testid="steady-state-scenario">{formatSig(s.capital)}</dd>
        </div>
        <div>
          <dt>Golden-rule savings rate (= α)</dt>
          <dd data-testid="golden-rule-rate">{gr.savings_rate}</dd>
        </div>
        <div>
          <dt>Steady-state consumption c*: s₀ / s₁ / golden</dt>
          <dd>
            {formatSig(b.consumption, 4)} / {formatSig(s.consumption, 4)} /{" "}
            {formatSig(gr.consumption, 4)}
          </dd>
        </div>
        <div>
          <dt>Convergence factor ρ (per year)</dt>
          <dd>{formatSig(conv.rho)}</dd>
        </div>
        <div>
          <dt>Half-life (linearised, near k*)</dt>
          <dd data-testid="half-life">{formatSig(conv.half_life_years, 4)} years</dd>
        </div>
      </dl>
      <p className="note" data-testid="golden-rule-sentence">
        {goldenRuleSentence(result)}
      </p>
      <h3>Scenario at key years</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Year</th>
              <th scope="col">Savings rate</th>
              <th scope="col">Capital k</th>
              <th scope="col">Consumption c</th>
              <th scope="col">Growth of Y/L to next year</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((t) => {
              const growth = scenario.output_per_worker_growth[t];
              return (
                <tr key={t}>
                  <th scope="row">{t}</th>
                  <td className="num">{scenario.savings_rate[t]}</td>
                  <td className="num">{formatSig(scenario.capital[t]!)}</td>
                  <td className="num">{formatSig(scenario.consumption[t]!)}</td>
                  <td className="num">
                    {growth === undefined ? "—" : `${formatSig(growth * 100, 4)}%`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="note">
        Capital-output ratio in the steady state: {formatSig(b.capital_output_ratio, 4)} years (s₀),{" "}
        {formatSig(s.capital_output_ratio, 4)} years (s₁). Capital, output and consumption are per
        effective worker, in model units.
      </p>
      <CsvDownloads response={result} />
    </>
  );
}

export function SolowAssumptions({ result }: Props) {
  return (
    <>
      <AssumptionsList assumptions={result.assumptions} />
      <h3>How it is computed</h3>
      <p className="note">{result.method_note}</p>
    </>
  );
}

export function SolowValidation({ result }: Props) {
  return (
    <>
      <ChecksTable checks={result.checks} />
      <p className="note">
        These checks describe this run only. The mathematical guarantees (a unique steady state,
        monotone convergence, the golden rule) are proved in SCIENTIFIC_VALIDATION.md and tested
        separately, along with empirical rounding bounds measured on a documented parameter grid.
      </p>
    </>
  );
}

/**
 * Memoised: the charts redraw only when the result changes, not on every keystroke in the
 * form (which re-renders the page but leaves the result object the same).
 */
export const SolowCharts = memo(SolowChartsView);
