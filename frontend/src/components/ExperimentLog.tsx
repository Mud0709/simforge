"use client";

import { useEffect, useState } from "react";

import { ApiError, type ExperimentRecord, listExperiments } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";

type Summary = {
  baseline_steady_state_capital?: number;
  scenario_steady_state_capital?: number;
  half_life_years?: number;
  analytical?: { range?: number };
  comparison?: { max_position_error?: number };
  methods?: Record<string, { position_order?: number | null }>;
};
type Inputs = {
  parameters?: Record<string, number>;
  solver?: { method?: string };
  methods?: string[];
};

/** One-line headline for a saved run; each model stores a different summary shape. */
export function keyResult(modelId: string, summary: Summary): string {
  if (modelId === "physics.projectile.integrators") {
    return Object.entries(summary.methods ?? {})
      .map(([m, s]) => `${m} p≈${s.position_order == null ? "n/a" : s.position_order.toFixed(2)}`)
      .join(", ");
  }
  if (modelId === "economy.solow") {
    const k0 = summary.baseline_steady_state_capital ?? NaN;
    const k1 = summary.scenario_steady_state_capital ?? NaN;
    const half = summary.half_life_years ?? NaN;
    return `k* ${formatSig(k0, 4)} → ${formatSig(k1, 4)}, half-life ${formatSig(half, 3)} y`;
  }
  const range = summary.analytical?.range;
  const err = summary.comparison?.max_position_error;
  if (range === undefined) return "—";
  return `range ${formatSig(range)} m, error ${formatExp(err ?? NaN)} m`;
}

export function ExperimentLog() {
  const [records, setRecords] = useState<ExperimentRecord[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listExperiments()
      .then(setRecords)
      .catch((err: unknown) =>
        setError(err instanceof ApiError ? err.message : "Unexpected error"),
      );
  }, []);

  if (error)
    return (
      <p className="api-error" role="alert">
        {error}
      </p>
    );
  if (!records) return <p className="note">Loading…</p>;
  if (records.length === 0)
    return <p className="card empty">No saved runs yet. Run a simulation to create one.</p>;

  return (
    <div className="card table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Created (UTC)</th>
            <th scope="col">Model</th>
            <th scope="col">v₀ (m/s)</th>
            <th scope="col">θ (°)</th>
            <th scope="col">b (kg/s)</th>
            <th scope="col">Solver(s)</th>
            <th scope="col">Key result</th>
            <th scope="col">Input hash</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => {
            const inputs = r.inputs as Inputs;
            const summary = r.summary as Summary;
            const p = inputs.parameters ?? {};
            return (
              <tr key={r.run_id}>
                <td>{r.created_at.slice(0, 19).replace("T", " ")}</td>
                <td>
                  {r.model_id} <span className="unit">v{r.model_version}</span>
                </td>
                <td className="num">{formatSig(p.initial_speed ?? NaN)}</td>
                <td className="num">{formatSig(p.launch_angle_deg ?? NaN)}</td>
                <td className="num">{formatSig(p.drag_coefficient ?? NaN)}</td>
                <td>{inputs.solver?.method ?? inputs.methods?.join(", ") ?? "—"}</td>
                <td>{keyResult(r.model_id, summary)}</td>
                <td>
                  <code title={r.input_hash}>{r.input_hash.slice(0, 10)}</code>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
