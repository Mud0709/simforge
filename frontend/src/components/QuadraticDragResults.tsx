"use client";

import type { Data } from "plotly.js";
import { memo, useMemo } from "react";

import type { ErrorMetric, ModelResponse, QuadraticDragResponse } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";
import { overlayFor, referenceTraces } from "@/lib/reference/overlay";
import { AssumptionsList } from "./AssumptionsList";
import { ChecksTable } from "./ChecksTable";
import { CsvDownloads } from "./CsvDownloads";
import { PlotlyChart } from "./PlotlyChart";
import { Reproducibility } from "./Reproducibility";

const NUMERICAL = "#ea580c";
const EXACT = "#2563eb";
const MODEL_ID = "physics.projectile.quadratic_drag";

type MetricKey = "flight_time" | "range" | "max_height" | "apex_time" | "impact_speed";
const METRICS: { key: MetricKey; label: string; unit: string }[] = [
  { key: "range", label: "Range", unit: "m" },
  { key: "flight_time", label: "Flight time", unit: "s" },
  { key: "max_height", label: "Maximum height", unit: "m" },
  { key: "apex_time", label: "Time to the top", unit: "s" },
  { key: "impact_speed", label: "Impact speed", unit: "m/s" },
];
/** The quantities the exact vertical flight gives (R3), in the order shown. */
const VERTICAL: { key: Exclude<MetricKey, "range">; label: string; unit: string }[] = [
  { key: "flight_time", label: "Flight time", unit: "s" },
  { key: "apex_time", label: "Time to the top", unit: "s" },
  { key: "max_height", label: "Maximum height", unit: "m" },
  { key: "impact_speed", label: "Impact speed", unit: "m/s" },
];

function relError(e: ErrorMetric): string {
  return e.relative === null || e.relative === undefined ? "n/a" : formatExp(e.relative);
}

type Props = { result: QuadraticDragResponse };

/** How the numerical values were obtained, written next to them. */
function numericalLabel({ numerical_note, numerical: n }: QuadraticDragResponse): string {
  return `${numerical_note}, ${n.method}, rtol = ${String(n.rtol)}, atol = ${String(n.atol)}`;
}

/** Visualisation: trajectory against the drag-free one, speed with v_t, the energy budget. */
function QuadraticDragChartsView({
  result,
  reference = null,
}: Props & { reference?: ModelResponse | null }) {
  const { numerical, series, terminal_speed: vT } = result;
  const overlay = useMemo(() => overlayFor(reference, MODEL_ID), [reference]);

  const trajectory = useMemo<Data[]>(
    () => [
      ...referenceTraces(overlay.trajectory),
      {
        x: series.x,
        y: series.y,
        name: `Quadratic drag (numerical, ${numerical.method})`,
        mode: "lines",
        line: { color: NUMERICAL, width: 2 },
      },
      {
        x: series.vacuum_x,
        y: series.vacuum_y,
        name: "No drag (exact)",
        mode: "lines",
        line: { color: EXACT, width: 2, dash: "dash" },
      },
    ],
    [series, numerical.method, overlay],
  );

  const speed = useMemo<Data[]>(() => {
    const traces: Data[] = [
      ...referenceTraces(overlay.speed),
      {
        x: series.t,
        y: series.speed,
        name: "Speed (numerical)",
        mode: "lines",
        line: { color: NUMERICAL, width: 2 },
      },
    ];
    if (vT !== null) {
      // A horizontal line across the flight: the speed drag and weight balance at.
      const end = series.t.at(-1) ?? 0;
      traces.push({
        x: [0, end],
        y: [vT, vT],
        name: "Terminal speed v_t (exact)",
        mode: "lines",
        line: { color: "#64748b", dash: "dot" },
      });
    }
    return traces;
  }, [series, vT, overlay]);

  const energy = useMemo<Data[]>(() => {
    const total = series.kinetic_energy.map(
      (ke, i) => ke + series.potential_energy[i]! + series.drag_work[i]!,
    );
    return [
      ...referenceTraces(overlay.energy),
      { x: series.t, y: series.kinetic_energy, name: "Kinetic", mode: "lines" },
      { x: series.t, y: series.potential_energy, name: "Potential", mode: "lines" },
      { x: series.t, y: series.drag_work, name: "Work against drag", mode: "lines" },
      {
        x: series.t,
        y: total,
        name: "KE + PE + W (constant for the true motion)",
        mode: "lines",
        line: { dash: "dash", color: "#64748b" },
      },
    ];
  }, [series, overlay]);

  return (
    <>
      <h3>Trajectory</h3>
      <PlotlyChart
        title="Trajectory: height against horizontal distance"
        data={trajectory}
        layout={{
          xaxis: { title: { text: "x (m)" } },
          yaxis: { title: { text: "y (m)" }, rangemode: "tozero" },
        }}
      />
      <p className="note">
        The dashed curve is the same launch with no drag, from the exact textbook formulas. With
        quadratic drag no exact 2-D solution exists, so the solid curve is numerical.
      </p>

      <h3>Speed</h3>
      <PlotlyChart
        title="Speed against time"
        data={speed}
        layout={{
          xaxis: { title: { text: "t (s)" } },
          yaxis: { title: { text: "Speed (m/s)" }, rangemode: "tozero" },
        }}
      />
      <p className="note">
        {vT === null
          ? "There is no terminal speed in a vacuum (c = 0): nothing balances the weight, so a " +
            "falling body keeps speeding up."
          : "The dotted line is the terminal speed v_t = √(mg/c), where drag balances the " +
            "weight. A long fall levels off towards it; the speed never exceeds max(v₀, v_t)."}
      </p>

      <h3>Energy budget</h3>
      <PlotlyChart
        title="Energy against time"
        data={energy}
        layout={{
          xaxis: { title: { text: "t (s)" } },
          yaxis: { title: { text: "Energy (J)" } },
        }}
      />
      <p className="note">
        The dashed line should be flat: the work against drag W is integrated separately from c|v|³,
        so any drift is numerical error (integration error, plus interpolation between solver
        steps).
      </p>
    </>
  );
}

/** Results: the numerical flight, the exact terminal speed, and the same launch with no drag. */
export function QuadraticDragSummary({ result }: Props) {
  const { numerical, vacuum, terminal_speed: vT } = result;
  return (
    <>
      <dl className="stats">
        {METRICS.filter((m) => m.key !== "apex_time").map(({ key, label, unit }) => (
          <div key={key}>
            <dt>{label} (numerical)</dt>
            <dd>
              {formatSig(numerical[key], 8)} {unit}
            </dd>
          </div>
        ))}
        <div>
          <dt>{vT === null ? "Terminal speed v_t" : "Terminal speed v_t (exact)"}</dt>
          <dd>{vT === null ? "none: no drag (c = 0)" : `${formatSig(vT, 8)} m/s`}</dd>
        </div>
      </dl>
      <p className="note">{numericalLabel(result)}</p>

      <h3>With and without drag</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Quantity</th>
              <th scope="col">Quadratic drag (numerical)</th>
              <th scope="col">No drag (exact)</th>
            </tr>
          </thead>
          <tbody>
            {METRICS.map(({ key, label, unit }) => (
              <tr key={key}>
                <th scope="row">
                  {label} <span className="unit">({unit})</span>
                </th>
                <td className="num">{formatSig(numerical[key], 8)}</td>
                <td className="num">{formatSig(vacuum[key], 8)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="note">{vacuum.method_note}</p>
      <CsvDownloads response={result} />
    </>
  );
}

/** Validation: the per-run checks, the exact vertical flight when there is one, the record. */
export function QuadraticDragValidation({ result }: Props) {
  const { numerical, diagnostics: d, vertical_reference: vr, metadata } = result;
  return (
    <>
      <ChecksTable checks={result.checks} />
      <p className="note">
        No exact solution exists for a 2-D flight with quadratic drag, so these checks test what
        must hold anyway: the energy balance, a conserved quantity of the motion (the hodograph
        invariant) and two proved bounds. They describe this run only; hover a row for how its limit
        is set.
      </p>

      {vr ? (
        <>
          <h3>Exact vertical flight vs numerical</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Quantity</th>
                  <th scope="col">Exact</th>
                  <th scope="col">Numerical</th>
                  <th scope="col">Abs. error</th>
                  <th scope="col">Rel. error</th>
                </tr>
              </thead>
              <tbody>
                {VERTICAL.map(({ key, label, unit }) => (
                  <tr key={key}>
                    <th scope="row">
                      {label} <span className="unit">({unit})</span>
                    </th>
                    <td className="num">{formatSig(vr.exact[key], 8)}</td>
                    <td className="num">{formatSig(numerical[key], 8)}</td>
                    <td className="num">{formatExp(vr[key].absolute)}</td>
                    <td className="num">{relError(vr[key])}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="note">{vr.method_note}</p>
        </>
      ) : (
        <p className="note">
          The exact comparison (rising with tan, falling with tanh) exists only for a launch at
          exactly 90°, where the motion is one-dimensional. Set the launch angle to 90 to see it.
        </p>
      )}

      <dl className="stats">
        <div>
          <dt>Max energy-balance residual</dt>
          <dd>{formatExp(d.max_energy_balance_residual)} × E₀</dd>
        </div>
        <div>
          <dt>Hodograph invariant residual</dt>
          <dd>
            {d.max_invariant_residual === null
              ? "not available"
              : `${formatExp(d.max_invariant_residual)} × max(1/vx²)`}
          </dd>
        </div>
        <div>
          <dt>Flight-time bound (proved)</dt>
          <dd>{formatSig(d.flight_time_bound, 6)} s</dd>
        </div>
        <div>
          <dt>Solver work</dt>
          <dd>
            {numerical.n_steps} steps, {numerical.n_rhs_evaluations} evaluations
          </dd>
        </div>
      </dl>
      <p className="note">{d.invariant_note}</p>

      <Reproducibility metadata={metadata} />
    </>
  );
}

/** Assumptions: what the model takes as given. */
export function QuadraticDragAssumptions({ result }: Props) {
  return (
    <>
      <p className="note">
        {result.model.name} · v{result.model.version}
      </p>
      <AssumptionsList assumptions={result.assumptions} />
    </>
  );
}

/** Memoised: the charts redraw only when the result (or the reference) changes. */
export const QuadraticDragCharts = memo(QuadraticDragChartsView);
