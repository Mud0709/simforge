"use client";

import { useEffect, useState } from "react";

import { ApiError, type ExperimentRecord, listExperiments } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";

type Summary = {
  analytical?: { range?: number };
  comparison?: { max_position_error?: number };
};
type Inputs = { parameters?: Record<string, number>; solver?: { method?: string } };

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
            <th scope="col">Solver</th>
            <th scope="col">Range (m)</th>
            <th scope="col">Max pos. error (m)</th>
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
                <td>{inputs.solver?.method ?? "—"}</td>
                <td className="num">{formatSig(summary.analytical?.range ?? NaN)}</td>
                <td className="num">{formatExp(summary.comparison?.max_position_error ?? NaN)}</td>
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
