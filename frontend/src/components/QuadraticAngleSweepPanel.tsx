"use client";

import { useMemo } from "react";

import {
  type QuadraticAngleSweepResponse,
  type QuadraticDragParameters,
  type SolverSettings,
  runQuadraticAngleSweep,
} from "@/lib/api/client";
import { spec } from "@/lib/fields";
import { formatSig } from "@/lib/format";
import { type SweepAdapter, SweepPanel } from "./AngleSweepPanel";
import { ChecksTable } from "./ChecksTable";
import { Reproducibility } from "./Reproducibility";
import type { ReferenceRun } from "./useReferenceRun";

/** The sweep's own checks (not aggregated from the 2.1 model's runs), by id. */
const SWEEP_OWN_CHECKS: readonly string[] = ["interior_peaks", "sweep_cost"];

const N_ANGLES = spec("QuadraticAngleSweepRequest", "n_angles", "Number of angles", "");

/** "42.98° ± 0.002° (estimate)": the uncertainty to one significant figure, labelled as what
 *  it is (an estimate, not a bound); just the angle when the model gives none (an edge). */
function bestAngleText(s: QuadraticAngleSweepResponse): string {
  const angle = `${s.best_angle_deg.toFixed(2)}°`;
  const u = s.best_angle_uncertainty_deg;
  return u === null ? angle : `${angle} ± ${formatSig(u, 1)}° (estimate)`;
}

/**
 * The quadratic-drag sweep (roadmap 2.2): every range is a numerical run, so the curve says
 * which solver made it, the best angle carries its estimated accuracy, and the exact
 * drag-free curve is drawn dashed for comparison. Sends the simulation's own parameters and
 * solver; the launch angle is ignored by the server.
 */
export function QuadraticAngleSweepPanel({
  parameters,
  solver,
  referenceRun,
  initialAngles,
  onAnglesChange,
  onSweep,
}: {
  parameters: QuadraticDragParameters;
  solver: SolverSettings;
  referenceRun?: ReferenceRun;
  initialAngles?: string;
  onAnglesChange?: (value: string) => void;
  onSweep?: (sweep: QuadraticAngleSweepResponse) => void;
}) {
  const adapter = useMemo<SweepAdapter<QuadraticAngleSweepResponse>>(
    () => ({
      modelId: "physics.projectile.quadratic_angle_sweep",
      run: (nAngles) => runQuadraticAngleSweep({ parameters, solver, n_angles: nAngles }),
      curveName: (s) => `Range (numerical, ${s.solver.method})`,
      bestAngleLabel: () => "Best angle (numerical)",
      bestAngleText,
      bestMarkerName: "Best angle (numerical)",
      vacuumCurve: (s) => s.vacuum_ranges,
      extraStats: (s) => {
        const peaks = s.checks.find((c) => c.id === "interior_peaks");
        return (
          peaks && (
            <div>
              <dt>Interior peaks on the grid</dt>
              <dd data-testid="peak-count">{peaks.value}</dd>
            </div>
          )
        );
      },
      notes: (s) => (
        <p className="note">
          {s.best_angle_note} The dashed curve is the same launch with no drag, from the exact
          formula.
        </p>
      ),
      angles: N_ANGLES,
    }),
    [parameters, solver],
  );
  return (
    <SweepPanel
      adapter={adapter}
      referenceRun={referenceRun}
      initialAngles={initialAngles}
      onAnglesChange={onAnglesChange}
      onSweep={onSweep}
    />
  );
}

/**
 * The sweep's checks, shown under Validation: each 2.1 check over every run of the sweep
 * (passed only if every run passed, with the value and limit of the run closest to its limit),
 * the sweep's own (peaks on the grid, the work used), and the sweep's run record.
 */
export function QuadraticSweepValidation({ sweep }: { sweep: QuadraticAngleSweepResponse }) {
  // Found by id, not by position, so the note stays true if the server reorders its checks.
  const own = SWEEP_OWN_CHECKS.flatMap((id) => sweep.checks.find((c) => c.id === id)?.label ?? []);
  return (
    <section aria-labelledby="sweep-checks-heading">
      <h3 id="sweep-checks-heading">Angle sweep: checks over every run</h3>
      <ChecksTable checks={sweep.checks} />
      <p className="note">
        The sweep made {sweep.n_runs} runs of the quadratic-drag model. Each of that model&apos;s
        checks is taken over every run it applies to: it passes only if each of them passed, and
        shows the value and limit of the run closest to its limit, at the angle named below.
        {own.length > 0 && ` The sweep's own checks are ${own.join(" and ")}.`}
      </p>
      <ul className="note">
        {sweep.checks.map((c) => (
          <li key={c.id}>
            <strong>{c.label}.</strong> {c.note}
          </li>
        ))}
      </ul>
      <Reproducibility metadata={sweep.metadata} />
    </section>
  );
}
