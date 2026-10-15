"use client";

import type { Data } from "plotly.js";
import { useMemo } from "react";

import type { ErrorMetric, ProjectileResponse } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";
import { AngleSweepPanel } from "./AngleSweepPanel";
import { PlotlyChart } from "./PlotlyChart";

const ANALYTICAL = "#2563eb";
const NUMERICAL = "#ea580c";

type MetricKey = "flight_time" | "range" | "max_height" | "impact_speed";
const METRICS: { key: MetricKey; label: string; unit: string }[] = [
  { key: "flight_time", label: "Flight time", unit: "s" },
  { key: "range", label: "Range", unit: "m" },
  { key: "max_height", label: "Maximum height", unit: "m" },
  { key: "impact_speed", label: "Impact speed", unit: "m/s" },
];

function relError(e: ErrorMetric): string {
  return e.relative === null || e.relative === undefined ? "n/a" : formatExp(e.relative);
}

export function ProjectileResults({ result }: { result: ProjectileResponse }) {
  const { analytical, numerical, comparison, series, metadata } = result;

  const trajectory = useMemo<Data[]>(
    () => [
      {
        x: series.x_analytical,
        y: series.y_analytical,
        name: "Analytical (exact)",
        mode: "lines",
        line: { color: ANALYTICAL, width: 2 },
      },
      {
        // Show every ~20th sample as a marker so both curves stay visible where they overlap.
        x: series.x_numerical.filter((_, i) => i % 20 === 0),
        y: series.y_numerical.filter((_, i) => i % 20 === 0),
        name: `Numerical (${numerical.method})`,
        mode: "markers",
        marker: { color: NUMERICAL, size: 7, symbol: "circle-open", line: { width: 2 } },
      },
    ],
    [series, numerical.method],
  );

  const energy = useMemo<Data[]>(() => {
    const total = series.kinetic_energy.map(
      (ke, i) => ke + series.potential_energy[i]! + series.drag_work[i]!,
    );
    return [
      { x: series.t, y: series.kinetic_energy, name: "Kinetic", mode: "lines" },
      { x: series.t, y: series.potential_energy, name: "Potential", mode: "lines" },
      { x: series.t, y: series.drag_work, name: "Work against drag", mode: "lines" },
      {
        x: series.t,
        y: total,
        name: "KE + PE + W (conserved)",
        mode: "lines",
        line: { dash: "dash", color: "#64748b" },
      },
    ];
  }, [series]);

  return (
    <div className="results">
      <section className="card" aria-labelledby="summary-heading">
        <h2 id="summary-heading">Analytical vs numerical</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Quantity</th>
                <th scope="col">Analytical</th>
                <th scope="col">Numerical</th>
                <th scope="col">Abs. error</th>
                <th scope="col">Rel. error</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map(({ key, label, unit }) => (
                <tr key={key}>
                  <th scope="row">
                    {label} <span className="unit">({unit})</span>
                  </th>
                  <td className="num">{formatSig(analytical[key], 8)}</td>
                  <td className="num">{formatSig(numerical[key], 8)}</td>
                  <td className="num">{formatExp(comparison[key].absolute)}</td>
                  <td className="num">{relError(comparison[key])}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <dl className="stats">
          <div>
            <dt>Max position error (at solver steps)</dt>
            <dd data-testid="max-position-error">{formatExp(comparison.max_position_error)} m</dd>
          </div>
          <div>
            <dt>Max energy-balance residual</dt>
            <dd>{formatExp(comparison.max_energy_balance_residual)} × E₀</dd>
          </div>
          <div>
            <dt>Solver work</dt>
            <dd>
              {numerical.n_steps} steps, {numerical.n_rhs_evaluations} evaluations
            </dd>
          </div>
        </dl>
        <p className="note">{analytical.method_note}</p>
      </section>

      <section className="card" aria-labelledby="trajectory-heading">
        <h2 id="trajectory-heading">Trajectory</h2>
        <PlotlyChart
          title="Trajectory: height against horizontal distance"
          data={trajectory}
          layout={{
            xaxis: { title: { text: "x (m)" } },
            yaxis: { title: { text: "y (m)" }, rangemode: "tozero" },
          }}
        />
      </section>

      {/* Keyed by run, so a new simulation clears any earlier sweep. */}
      <AngleSweepPanel key={metadata.run_id} parameters={result.parameters} />

      <section className="card" aria-labelledby="energy-heading">
        <h2 id="energy-heading">Energy budget</h2>
        <PlotlyChart
          title="Energy against time"
          data={energy}
          layout={{
            xaxis: { title: { text: "t (s)" } },
            yaxis: { title: { text: "Energy (J)" } },
          }}
        />
        <p className="note">
          The dashed line should be flat: energy lost to drag is accounted for, so any drift is
          integration error.
        </p>
      </section>

      <section className="card" aria-labelledby="assumptions-heading">
        <h2 id="assumptions-heading">Model assumptions</h2>
        <p className="note">
          {result.model.name} · v{result.model.version}
        </p>
        <ul className="assumptions">
          {result.assumptions.map((a) => (
            <li key={a.id}>{a.statement}</li>
          ))}
        </ul>
      </section>

      <section className="card" aria-labelledby="meta-heading">
        <h2 id="meta-heading">Reproducibility</h2>
        <dl className="meta">
          <dt>Run ID</dt>
          <dd>
            <code>{metadata.run_id}</code>
          </dd>
          <dt>Input hash</dt>
          <dd>
            <code title={metadata.input_hash}>{metadata.input_hash.slice(0, 16)}…</code>
          </dd>
          <dt>Environment</dt>
          <dd>
            SimForge {metadata.simforge_version} · Python {metadata.python_version} · NumPy{" "}
            {metadata.numpy_version} · SciPy {metadata.scipy_version}
          </dd>
          <dt>Compute time</dt>
          <dd>{formatSig(metadata.elapsed_ms, 3)} ms</dd>
          <dt>Saved to experiment log</dt>
          <dd>{metadata.experiment_saved ? "Yes" : "No"}</dd>
        </dl>
      </section>
    </div>
  );
}
