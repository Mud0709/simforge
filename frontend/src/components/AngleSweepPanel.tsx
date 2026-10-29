"use client";

import type { Data } from "plotly.js";
import { type ReactNode, useMemo, useState } from "react";

import {
  ApiError,
  type AngleSweepResponse,
  type ProjectileParameters,
  runAngleSweep,
} from "@/lib/api/client";
import type { ResponseOf } from "@/lib/api/models";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import { formatSig } from "@/lib/format";
import { overlayFor, referenceTraces } from "@/lib/reference/overlay";
import { CsvDownloads } from "./CsvDownloads";
import { PlotlyChart } from "./PlotlyChart";
import { ComparisonTable } from "./ComparisonTable";
import { NumberField } from "./NumberField";
import { versionWarning } from "./ReferenceRunPanel";
import type { ReferenceRun } from "./useReferenceRun";

/** The models whose response is a range-against-angle sweep. */
export type SweepModelId =
  "physics.projectile.angle_sweep" | "physics.projectile.quadratic_angle_sweep";
export type SweepResponse = ResponseOf[SweepModelId];

/**
 * What one sweep model brings to the shared panel (roadmap 2.2, D12): how to run it and how
 * its numbers are labelled. Everything else (the button, the chart, the stats layout, the
 * reference run and the CSV) is the same for every drag law.
 */
export interface SweepAdapter<R extends SweepResponse> {
  modelId: SweepModelId;
  /** Runs the sweep; `nAngles` is set only when the adapter has an `angles` field. */
  run: (nAngles?: number) => Promise<R>;
  /** The computed range curve's legend entry, saying how it was obtained. */
  curveName: (sweep: R) => string;
  bestAngleLabel: (sweep: R) => string;
  bestAngleText: (sweep: R) => string;
  bestMarkerName: string;
  /** The exact drag-free range at the same angles, drawn dashed with its best angle marked. */
  vacuumCurve?: (sweep: R) => number[];
  /** More stats after the vacuum optimum, inside the same list. */
  extraStats?: (sweep: R) => ReactNode;
  /** More notes after the method note. */
  notes?: (sweep: R) => ReactNode;
  /** A field to choose the number of angles, from the contract; absent: the server's default. */
  angles?: NumericFieldSpec;
}

const RANGE = "#2563eb";
const BEST = "#ea580c";
const EXACT = "#64748b";

/**
 * Range against launch angle for the current settings, and the angle that maximises it.
 * Uses the parameters of the simulation already on screen; only the angle is varied. A
 * reference sweep, if the page has one, is drawn faded under it, and a sweep can be pinned.
 */
export function SweepPanel<R extends SweepResponse>({
  adapter,
  referenceRun,
  initialAngles,
  onAnglesChange,
  onSweep,
}: {
  adapter: SweepAdapter<R>;
  referenceRun?: ReferenceRun;
  /** The number of angles to start from (a reopened run's, or the one typed before a new
   *  simulation remounted the panel); else the contract's default. */
  initialAngles?: string;
  /** Told about each edit of the number of angles, so the page can keep it across remounts. */
  onAnglesChange?: (value: string) => void;
  /** Told about each sweep, so the page can show its checks under Validation. */
  onSweep?: (sweep: R) => void;
}) {
  const [sweep, setSweep] = useState<R | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const field = adapter.angles;
  const [angles, setAngles] = useState(initialAngles ?? String(field?.default ?? ""));
  const [touched, setTouched] = useState(false);
  const anglesError = field ? validateField(field, angles) : null;

  async function run() {
    setTouched(true);
    if (anglesError) return;
    setRunning(true);
    setError(null);
    try {
      const result = await adapter.run(field ? Number(angles) : undefined);
      setSweep(result);
      onSweep?.(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }

  const reference = referenceRun?.response ?? null;
  const data = useMemo<Data[]>(() => {
    if (!sweep) return [];
    const vacuum = adapter.vacuumCurve?.(sweep);
    return [
      ...referenceTraces(overlayFor(reference, adapter.modelId).range),
      {
        x: sweep.angles_deg,
        y: sweep.ranges,
        name: adapter.curveName(sweep),
        mode: "lines",
        line: { color: RANGE, width: 2 },
      },
      ...(vacuum
        ? [
            {
              x: sweep.angles_deg,
              y: vacuum,
              name: "No drag (exact)",
              mode: "lines",
              line: { color: EXACT, width: 2, dash: "dash" },
            } satisfies Data,
          ]
        : []),
      {
        x: [sweep.best_angle_deg],
        y: [sweep.best_range],
        name: adapter.bestMarkerName,
        mode: "markers",
        marker: { color: BEST, size: 10 },
      },
      ...(vacuum
        ? [
            {
              x: [sweep.vacuum_best_angle_deg],
              y: [sweep.vacuum_best_range],
              name: "Best angle, no drag (exact)",
              mode: "markers",
              marker: { color: EXACT, size: 9, symbol: "diamond" },
            } satisfies Data,
          ]
        : []),
    ];
  }, [sweep, reference, adapter]);

  return (
    <section aria-labelledby="sweep-heading">
      <h3 id="sweep-heading">Range against launch angle</h3>
      {!sweep && (
        <>
          <p className="note">
            Keep everything else the same and vary only the launch angle from 0° to 90°. Which angle
            throws furthest?
          </p>
          {field && (
            <NumberField
              field={field}
              value={angles}
              error={touched ? anglesError : null}
              onChange={(value) => {
                setAngles(value);
                onAnglesChange?.(value);
              }}
            />
          )}
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
              <dt>{adapter.bestAngleLabel(sweep)}</dt>
              <dd data-testid="best-angle">{adapter.bestAngleText(sweep)}</dd>
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
            {adapter.extraStats?.(sweep)}
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
          {adapter.notes?.(sweep)}
          {referenceRun && <SweepReference referenceRun={referenceRun} sweep={sweep} />}
          <CsvDownloads response={sweep} />
        </>
      )}
    </section>
  );
}

/** The linear-drag sweep (roadmap 1.5): exact ranges, so no solver and no estimate. */
export function AngleSweepPanel({
  parameters,
  referenceRun,
}: {
  parameters: ProjectileParameters;
  referenceRun?: ReferenceRun;
}) {
  const adapter = useMemo<SweepAdapter<AngleSweepResponse>>(() => {
    const drag = (parameters.drag_coefficient ?? 0) > 0;
    return {
      modelId: "physics.projectile.angle_sweep",
      run: () => runAngleSweep({ parameters }),
      curveName: () => "Range (analytical)",
      bestAngleLabel: () => `Best angle${drag ? " (with drag)" : ""}`,
      bestAngleText: (s) => `${s.best_angle_deg.toFixed(2)}°`,
      bestMarkerName: "Best angle",
    };
  }, [parameters]);
  return <SweepPanel adapter={adapter} referenceRun={referenceRun} />;
}

/**
 * The sweep's own pin control, a warning if a reference sweep ran on another version, and how
 * this sweep differs from a reference sweep.
 */
function SweepReference({
  referenceRun,
  sweep,
}: {
  referenceRun: ReferenceRun;
  sweep: SweepResponse;
}) {
  const ref = referenceRun.reference;
  const pinned = ref?.status === "ready" && ref.runId === sweep.metadata.run_id;
  const warning = versionWarning(referenceRun.response, sweep);
  return (
    <>
      {warning && <p className="api-error">{warning}</p>}
      {referenceRun.response && (
        <ComparisonTable reference={referenceRun.response} current={sweep} />
      )}
      {pinned ? (
        <p className="note">This sweep is the reference run.</p>
      ) : (
        <button type="button" className="secondary" onClick={() => referenceRun.pin(sweep)}>
          Pin sweep as reference run
        </button>
      )}
    </>
  );
}
