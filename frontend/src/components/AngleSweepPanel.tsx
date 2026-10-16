"use client";

import type { Data } from "plotly.js";
import { useMemo, useState } from "react";

import {
  ApiError,
  type AngleSweepResponse,
  type ProjectileParameters,
  runAngleSweep,
} from "@/lib/api/client";
import { formatSig } from "@/lib/format";
import { PlotlyChart } from "./PlotlyChart";

/**
 * Range against launch angle for the current settings, and the angle that maximises it.
 * Uses the parameters of the simulation already on screen; only the angle is varied.
 */
export function AngleSweepPanel({ parameters }: { parameters: ProjectileParameters }) {
  const [sweep, setSweep] = useState<AngleSweepResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function run() {
    setRunning(true);
    setError(null);
    try {
      setSweep(await runAngleSweep({ parameters }));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }

  const data = useMemo<Data[]>(() => {
    if (!sweep) return [];
    return [
      {
        x: sweep.angles_deg,
        y: sweep.ranges,
        name: "Range (exact)",
        mode: "lines",
        line: { color: "#2563eb", width: 2 },
      },
      {
        x: [sweep.best_angle_deg],
        y: [sweep.best_range],
        name: "Best angle",
        mode: "markers",
        marker: { color: "#ea580c", size: 10 },
      },
    ];
  }, [sweep]);

  const drag = (parameters.drag_coefficient ?? 0) > 0;

  return (
    <section aria-labelledby="sweep-heading">
      <h3 id="sweep-heading">Range against launch angle</h3>
      {!sweep && (
        <>
          <p className="note">
            Keep everything else the same and vary only the launch angle from 0° to 90°. Which angle
            throws furthest?
          </p>
          <button type="button" onClick={run} disabled={running}>
            {running ? "Sweeping…" : "Sweep launch angle"}
          </button>
        </>
      )}
      {error && (
        <p className="api-error" role="alert">
          {error}
        </p>
      )}
      {sweep && (
        <>
          <dl className="stats">
            <div>
              <dt>Best angle{drag ? " (with drag)" : ""}</dt>
              <dd data-testid="best-angle">{sweep.best_angle_deg.toFixed(2)}°</dd>
            </div>
            <div>
              <dt>Maximum range</dt>
              <dd data-testid="best-range">{formatSig(sweep.best_range, 6)} m</dd>
            </div>
            <div>
              <dt>Best angle in a vacuum (formula)</dt>
              <dd data-testid="vacuum-angle">
                {sweep.vacuum_best_angle_deg.toFixed(2)}° · {formatSig(sweep.vacuum_best_range, 6)}{" "}
                m
              </dd>
            </div>
          </dl>
          <PlotlyChart
            title="Range against launch angle"
            data={data}
            layout={{
              xaxis: { title: { text: "Launch angle (°)" }, range: [0, 90], dtick: 15 },
              yaxis: { title: { text: "Range (m)" }, rangemode: "tozero" },
            }}
          />
          <p className="note">{sweep.method_note}</p>
        </>
      )}
    </section>
  );
}
