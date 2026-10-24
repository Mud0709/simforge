/**
 * What a reference run draws on each chart (roadmap 1.6, D7). Each model's curves are kept as
 * named series with units, taken from the response's own `units` map, so a later step could
 * match series across models by name and unit. For now a reference is drawn only over runs
 * of the same model (`overlayFor`). Values are copied as they are, never recomputed.
 */

import type { Data } from "plotly.js";

import type { ModelResponse } from "@/lib/api/client";
import { type ModelId, isModelResponse } from "@/lib/api/models";

/** The legend entry every reference curve shares. */
export const REFERENCE_TRACE_NAME = "reference run";

/** One axis of a curve: what it is, its unit (when the model gives one), its values. */
export interface Axis {
  name: string;
  unit?: string;
  values: number[];
}

/** One curve of the reference run. */
export interface NamedSeries {
  label: string;
  x: Axis;
  y: Axis;
}

/** The reference's curves for each chart of its model, by chart id. */
export type ChartSeries = Partial<Record<string, NamedSeries[]>>;

type Units = Record<string, string> | undefined;

function axis(name: string, values: number[], units: Units, unitKey: string): Axis {
  const unit = units?.[unitKey];
  return unit ? { name, unit, values } : { name, values };
}

/** Pairs of (x, y) with a missing y (a diverged run, say) left out. */
function present(xs: number[], ys: (number | null)[]): [number[], number[]] {
  const keep = ys.map((y, i) => [xs[i], y] as const).filter(([, y]) => y !== null);
  return [keep.map(([x]) => x as number), keep.map(([, y]) => y as number)];
}

/** Every curve the reference can draw, by chart id; {} for a model without charts to overlay. */
export function referenceSeries(r: ModelResponse): ChartSeries {
  if (isModelResponse(r, "physics.projectile")) {
    const { series: s, units: u } = r;
    const t = axis("t", s.t, u, "t");
    return {
      // What the reference's solver computed, like its energies below (the exact curve depends
      // on the physical inputs alone, so it would hide a change of solver or tolerance).
      trajectory: [
        {
          label: "numerical trajectory",
          x: axis("x_numerical", s.x_numerical, u, "x"),
          y: axis("y_numerical", s.y_numerical, u, "y"),
        },
      ],
      energy: [
        { label: "kinetic energy", x: t, y: axis("kinetic_energy", s.kinetic_energy, u, "energy") },
        {
          label: "potential energy",
          x: t,
          y: axis("potential_energy", s.potential_energy, u, "energy"),
        },
        { label: "work against drag", x: t, y: axis("drag_work", s.drag_work, u, "energy") },
      ],
    };
  }
  if (isModelResponse(r, "physics.projectile.angle_sweep")) {
    const u = r.units;
    return {
      range: [
        {
          label: "range",
          x: axis("angle", r.angles_deg, u, "angle"),
          y: axis("range", r.ranges, u, "range"),
        },
      ],
    };
  }
  if (isModelResponse(r, "physics.projectile.integrators")) {
    const u = r.units;
    const errors = (q: "position" | "velocity"): NamedSeries[] =>
      r.results.map((m) => {
        const [h, e] = present(
          m.runs.map((run) => run.h),
          m.runs.map((run) => run[`max_${q}_error`]),
        );
        return {
          label: m.name,
          x: axis("h", h, u, "h"),
          y: axis(`max_${q}_error`, e, u, `${q}_error`),
        };
      });
    return {
      position_error: errors("position"),
      velocity_error: errors("velocity"),
      trajectories: [
        {
          label: "exact trajectory",
          x: axis("x", r.exact_trajectory.x, u, "x"),
          y: axis("y", r.exact_trajectory.y, u, "y"),
        },
      ],
    };
  }
  if (isModelResponse(r, "economy.solow")) {
    const u = r.units;
    const years = axis("year", r.years, u, "years");
    const paths = (key: "capital" | "consumption" | "output_per_worker_index"): NamedSeries[] =>
      (["baseline", "scenario"] as const).map((path) => ({
        label: path,
        x: years,
        y: axis(key, r[path][key], u, key),
      }));
    return {
      capital: paths("capital"),
      consumption: paths("consumption"),
      output_per_worker: paths("output_per_worker_index"),
    };
  }
  // The dataset profile is compared in a table, not on its charts.
  return {};
}

/** The reference's curves for a chart of `modelId`, or {} if it is from another model. */
export function overlayFor(
  reference: ModelResponse | null | undefined,
  modelId: ModelId,
): ChartSeries {
  return reference && isModelResponse(reference, modelId) ? referenceSeries(reference) : {};
}

const FADED = "#94a3b8";

/**
 * Plotly traces for a chart's reference curves: faded, dashed, one shared legend entry.
 * Put them first in the chart's data, so the current run's curves are drawn on top.
 */
export function referenceTraces(series: readonly NamedSeries[] | undefined): Data[] {
  return (series ?? []).map((s, i) => ({
    x: s.x.values,
    y: s.y.values,
    // The label goes through `text`, never into the template, so it is shown as plain text.
    text: s.x.values.map(() => s.label),
    hovertemplate: `%{text}<br>(%{x}, %{y})<extra>${REFERENCE_TRACE_NAME}</extra>`,
    name: REFERENCE_TRACE_NAME,
    legendgroup: "reference",
    showlegend: i === 0,
    mode: "lines",
    opacity: 0.55,
    line: { color: FADED, width: 2, dash: "dash" },
  }));
}
