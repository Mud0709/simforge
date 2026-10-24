"use client";

import type { Data } from "plotly.js";
import { memo, useMemo } from "react";

import type { IntegratorStudyResponse, MethodStudyResult, ModelResponse } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";
import { overlayFor, referenceTraces } from "@/lib/reference/overlay";
import { AssumptionsList } from "./AssumptionsList";
import { CsvDownloads } from "./CsvDownloads";
import { PlotlyChart } from "./PlotlyChart";

const COLORS: Record<MethodStudyResult["method"], string> = {
  euler: "#dc2626",
  rk4: "#2563eb",
  verlet: "#16a34a",
};

type Quantity = "position" | "velocity";

// Reference lines pass through the finest fitted point. Drawn there they sit exactly on
// top of data that follow the theory, which hides them, so they are shifted down by this
// factor. A vertical shift on log axes does not change the slope.
export const REFERENCE_OFFSET = 0.2;

function convergenceTraces(results: MethodStudyResult[], q: Quantity): Data[] {
  const traces: Data[] = [];
  for (const m of results) {
    const color = COLORS[m.method];
    const runs = m.runs.filter((r) => r[`max_${q}_error`] !== null);
    const inFit = runs.filter((r) => r[`in_${q}_fit`]);
    const excluded = runs.filter((r) => !r[`in_${q}_fit`]);
    traces.push({
      x: inFit.map((r) => r.h),
      y: inFit.map((r) => r[`max_${q}_error`] as number),
      name: `${m.name}: in fit`,
      legendgroup: m.method,
      mode: "lines+markers",
      line: { color, width: 1.5 },
      marker: { color, size: 8 },
    });
    if (excluded.length > 0) {
      traces.push({
        x: excluded.map((r) => r.h),
        y: excluded.map((r) => r[`max_${q}_error`] as number),
        text: excluded.map((r) => r.exclusion_reason ?? ""),
        hovertemplate: "h = %{x:.3e} s<br>error = %{y:.3e}<br>excluded: %{text}<extra></extra>",
        name: `${m.name}: excluded`,
        legendgroup: m.method,
        showlegend: false,
        mode: "markers",
        marker: { color, size: 9, symbol: "circle-open", line: { width: 2 } },
      });
    }
    const ref = m[`${q}_reference`];
    if (ref) {
      traces.push({
        x: ref.h,
        y: ref.error.map((e) => e * REFERENCE_OFFSET),
        name: `slope ${ref.order} (theory, shifted ×${REFERENCE_OFFSET})`,
        legendgroup: m.method,
        mode: "lines",
        line: { color, dash: "dot", width: 2 },
        hoverinfo: "skip",
      });
    }
  }
  return traces;
}

function FitCell({ fit }: { fit: MethodStudyResult["position_fit"] }) {
  if (!fit) return <td className="num">not fitted</td>;
  return <td className="num">{fit.order.toFixed(3)}</td>;
}

type Props = { result: IntegratorStudyResponse };

const logAxes = (yTitle: string) => ({
  xaxis: {
    type: "log" as const,
    title: { text: "Time step h (s)" },
    exponentformat: "power" as const,
  },
  yaxis: { type: "log" as const, title: { text: yTitle }, exponentformat: "power" as const },
});

/** Visualisation: convergence plots and trajectories, over any reference run's (faded). */
function IntegratorChartsView({
  result,
  reference = null,
}: Props & { reference?: ModelResponse | null }) {
  const overlay = useMemo(
    () => overlayFor(reference, "physics.projectile.integrators"),
    [reference],
  );
  const position = useMemo(
    () => [
      ...referenceTraces(overlay.position_error),
      ...convergenceTraces(result.results, "position"),
    ],
    [result, overlay],
  );
  const velocity = useMemo(
    () => [
      ...referenceTraces(overlay.velocity_error),
      ...convergenceTraces(result.results, "velocity"),
    ],
    [result, overlay],
  );
  const trajectories = useMemo<Data[]>(
    () => [
      ...referenceTraces(overlay.trajectories),
      {
        x: result.exact_trajectory.x,
        y: result.exact_trajectory.y,
        name: "Exact",
        mode: "lines",
        line: { color: "#64748b", width: 3 },
      },
      ...result.results
        .filter((m) => m.trajectory)
        .map<Data>((m) => ({
          x: m.trajectory!.x,
          y: m.trajectory!.y,
          name: `${m.name}, h = ${formatSig(m.trajectory!.h, 3)} s`,
          mode: "lines",
          line: { color: COLORS[m.method], width: 1.5, dash: "dash" },
        })),
    ],
    [result, overlay],
  );

  return (
    <>
      <h3>Position error against time step</h3>
      <PlotlyChart
        title="Log-log convergence plot of maximum position error against time step"
        data={position}
        height={520}
        layout={{ ...logAxes("Max position error over grid nodes (m)") }}
      />
      <p className="note">
        Filled markers are in the fit; open markers are excluded (hover for the reason). Dotted
        lines have the theoretical slope: they start at the finest fitted point and are shifted down
        ×{REFERENCE_OFFSET} so they don&apos;t hide the data. They are guides, not fits. On log-log
        axes, error ∝ hᵖ appears as a straight line of slope p.
      </p>

      <h3>Velocity error against time step</h3>
      <PlotlyChart
        title="Log-log convergence plot of maximum velocity error against time step"
        data={velocity}
        height={520}
        layout={{ ...logAxes("Max velocity error over grid nodes (m/s)") }}
      />

      <h3>Trajectories at the coarsest stable step</h3>
      <PlotlyChart
        title="Trajectories from each method compared with the exact solution"
        data={trajectories}
        layout={{
          xaxis: { title: { text: "x (m)" } },
          yaxis: { title: { text: "y (m)" } },
        }}
      />
    </>
  );
}

/** Results: the fitted convergence orders. */
export function IntegratorOrders({ result }: Props) {
  return (
    <>
      <h3>Convergence orders</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Method</th>
              <th scope="col">Theory</th>
              <th scope="col">Fitted (position)</th>
              <th scope="col">Points</th>
              <th scope="col">Fit range h (s)</th>
              <th scope="col">R²</th>
              <th scope="col">Fitted (velocity)</th>
              <th scope="col">Stable for kh ≤</th>
            </tr>
          </thead>
          <tbody>
            {result.results.map((m) => (
              <tr key={m.method} data-testid={`order-${m.method}`}>
                <th scope="row">{m.name}</th>
                <td className="num">{m.theoretical_order}</td>
                <FitCell fit={m.position_fit} />
                <td className="num">{m.position_fit?.n_points ?? 0}</td>
                <td className="num">
                  {m.position_fit
                    ? `${formatExp(m.position_fit.h_min, 3)} – ${formatExp(m.position_fit.h_max, 3)}`
                    : "—"}
                </td>
                <td className="num">
                  {m.position_fit ? m.position_fit.r_squared.toFixed(6) : "—"}
                </td>
                <FitCell fit={m.velocity_fit} />
                <td className="num">
                  {m.stability_limit_kh === null ? "all kh" : formatSig(m.stability_limit_kh, 5)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.results
        .filter((m) => m.fit_note)
        .map((m) => (
          <p key={m.method} className="note">
            <strong>{m.name}:</strong> {m.fit_note}
          </p>
        ))}
      <p className="note">
        For Euler and RK4 the velocity error is exactly k × the position error (a conserved linear
        invariant), so their velocity order is not independent evidence. Horizon T ={" "}
        {formatSig(result.horizon, 6)} s, k = {formatSig(result.k, 6)} s⁻¹.
      </p>
      <CsvDownloads response={result} />
    </>
  );
}

/** Validation: the pre-declared fit rule, every run with its inclusion decision, and the
 *  record of this run. */
export function IntegratorValidation({ result }: Props) {
  return (
    <>
      <p className="note">
        <strong>Fit rule.</strong> {result.fit_rule.description}
      </p>
      {result.results.map((m) => (
        // The heading sits outside <summary>: a summary is a button to screen readers, and
        // headings inside it do not appear in heading navigation.
        <div key={m.method} className="runs">
          <h3>All runs: {m.name}</h3>
          <details>
            <summary>Show the {m.runs.length} runs</summary>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th scope="col">h (s)</th>
                    <th scope="col">N</th>
                    <th scope="col">kh</th>
                    <th scope="col">R(−kh)</th>
                    <th scope="col">Stability</th>
                    <th scope="col">Max pos. err (m)</th>
                    <th scope="col">Max vel. err (m/s)</th>
                    <th scope="col">Local order</th>
                    <th scope="col">Fit</th>
                  </tr>
                </thead>
                <tbody>
                  {m.runs.map((r, i) => {
                    const local = i > 0 ? m.position_local_orders[i - 1] : null;
                    return (
                      <tr key={r.h}>
                        <td className="num">{formatExp(r.h, 4)}</td>
                        <td className="num">{r.n_steps}</td>
                        <td className="num">{formatSig(r.kh, 3)}</td>
                        <td className="num">{formatSig(r.amplification_factor, 4)}</td>
                        <td>{r.diverged ? `diverged at step ${r.n_completed}` : r.stability}</td>
                        <td className="num">
                          {r.max_position_error === null ? "—" : formatExp(r.max_position_error, 3)}
                        </td>
                        <td className="num">
                          {r.max_velocity_error === null ? "—" : formatExp(r.max_velocity_error, 3)}
                        </td>
                        <td className="num">
                          {local === null || local === undefined ? "—" : local.toFixed(3)}
                        </td>
                        <td>{r.in_position_fit ? "✓" : r.exclusion_reason}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </details>
        </div>
      ))}
      <p className="note">
        Run <code>{result.metadata.run_id}</code> · input hash{" "}
        <code title={result.metadata.input_hash}>{result.metadata.input_hash.slice(0, 12)}…</code> ·{" "}
        {formatSig(result.metadata.elapsed_ms, 3)} ms · NumPy {result.metadata.numpy_version}
      </p>
    </>
  );
}

/** Assumptions of the study. */
export function IntegratorAssumptions({ result }: Props) {
  return <AssumptionsList assumptions={result.assumptions} />;
}

/**
 * Memoised: the charts redraw only when the result changes, not on every keystroke in the
 * form (which re-renders the page but leaves the result object the same).
 */
export const IntegratorCharts = memo(IntegratorChartsView);
