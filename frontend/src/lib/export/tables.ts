/**
 * What each model exports as CSV: one table per chart or table on screen, built from the
 * response already in the page (roadmap 1.6, D3). Values are copied as they are: nothing is
 * recomputed or rounded here. Units come from the response's own `units` map.
 */

import type {
  AngleSweepResponse,
  IntegratorStudyResponse,
  ProfileResponse,
  ProjectileResponse,
  QuadraticAngleSweepResponse,
  QuadraticDragResponse,
  SolowResponse,
} from "@/lib/api/client";
import type { Cell, Column, Table } from "./csv";

type Units = Record<string, string> | undefined;

/** A column whose unit is looked up in the response's units map under `unitKey`. */
function col(name: string, values: readonly Cell[], units: Units, unitKey: string): Column {
  const unit = units?.[unitKey];
  return unit ? { name, unit, values } : { name, values };
}

export function projectileTables(r: ProjectileResponse): Table[] {
  const { series: s, units: u } = r;
  return [
    {
      name: "trajectory",
      label: "trajectory",
      columns: [
        col("t", s.t, u, "t"),
        col("x_analytical", s.x_analytical, u, "x"),
        col("y_analytical", s.y_analytical, u, "y"),
        col("x_numerical", s.x_numerical, u, "x"),
        col("y_numerical", s.y_numerical, u, "y"),
        col("speed_numerical", s.speed_numerical, u, "speed"),
      ],
    },
    {
      name: "energy",
      label: "energy budget",
      columns: [
        col("t", s.t, u, "t"),
        col("kinetic_energy", s.kinetic_energy, u, "energy"),
        col("potential_energy", s.potential_energy, u, "energy"),
        col("drag_work", s.drag_work, u, "energy"),
      ],
    },
  ];
}

/** One table per chart. The drag-free trajectory has its own time grid (as many points,
 *  over its longer flight), so it keeps its own time column, vacuum_t, beside the drag run's. */
export function quadraticDragTables(r: QuadraticDragResponse): Table[] {
  const { series: s, units: u } = r;
  const t = col("t", s.t, u, "t");
  return [
    {
      name: "trajectory",
      label: "trajectory",
      columns: [
        t,
        col("x", s.x, u, "x"),
        col("y", s.y, u, "y"),
        col("vacuum_t", s.vacuum_t, u, "t"),
        col("vacuum_x", s.vacuum_x, u, "x"),
        col("vacuum_y", s.vacuum_y, u, "y"),
      ],
    },
    { name: "speed", label: "speed", columns: [t, col("speed", s.speed, u, "speed")] },
    {
      name: "energy",
      label: "energy budget",
      columns: [
        t,
        col("kinetic_energy", s.kinetic_energy, u, "energy"),
        col("potential_energy", s.potential_energy, u, "energy"),
        col("drag_work", s.drag_work, u, "energy"),
      ],
    },
  ];
}

export function angleSweepTables(r: AngleSweepResponse): Table[] {
  const u = r.units;
  return [
    {
      name: "range_vs_angle",
      label: "range against angle",
      columns: [
        col("angle", r.angles_deg, u, "angle"),
        col("range", r.ranges, u, "range"),
        col("flight_time", r.flight_times, u, "flight_time"),
        col("max_height", r.max_heights, u, "max_height"),
      ],
    },
  ];
}

/** As the linear sweep, plus the exact drag-free range at the same angles. */
export function quadraticAngleSweepTables(r: QuadraticAngleSweepResponse): Table[] {
  const u = r.units;
  return [
    {
      name: "range_vs_angle",
      label: "range against angle",
      columns: [
        col("angle", r.angles_deg, u, "angle"),
        col("range", r.ranges, u, "range"),
        col("flight_time", r.flight_times, u, "flight_time"),
        col("max_height", r.max_heights, u, "max_height"),
        col("vacuum_range", r.vacuum_ranges, u, "vacuum_range"),
      ],
    },
  ];
}

export function integratorTables(r: IntegratorStudyResponse): Table[] {
  const u = r.units;
  const runs: Table[] = r.results.map((m) => {
    const of = <K extends keyof (typeof m.runs)[number]>(k: K) => m.runs.map((run) => run[k]);
    return {
      name: `runs_${m.method}`,
      label: `${m.method} runs`,
      columns: [
        col("h", of("h"), u, "h"),
        col("n_steps", of("n_steps"), u, "n_steps"),
        col("kh", of("kh"), u, "kh"),
        col("stability", of("stability"), u, "stability"),
        col("diverged", of("diverged"), u, "diverged"),
        col("max_position_error", of("max_position_error"), u, "position_error"),
        col("max_velocity_error", of("max_velocity_error"), u, "velocity_error"),
        col("final_position_error", of("final_position_error"), u, "position_error"),
        col("final_velocity_error", of("final_velocity_error"), u, "velocity_error"),
        col("in_position_fit", of("in_position_fit"), u, "in_position_fit"),
        col("in_velocity_fit", of("in_velocity_fit"), u, "in_velocity_fit"),
        col("exclusion_reason", of("exclusion_reason"), u, "exclusion_reason"),
      ],
    };
  });
  // The trajectories share no x: each is an (x, y) pair, sampled at its own step.
  const pairs: Column[] = [
    col("exact_x", r.exact_trajectory.x, u, "x"),
    col("exact_y", r.exact_trajectory.y, u, "y"),
  ];
  for (const m of r.results) {
    if (!m.trajectory) continue;
    const step = `(h = ${String(m.trajectory.h)}${u?.h ? ` ${u.h}` : ""})`;
    pairs.push(col(`${m.method}_x ${step}`, m.trajectory.x, u, "x"));
    pairs.push(col(`${m.method}_y ${step}`, m.trajectory.y, u, "y"));
  }
  return [...runs, { name: "trajectories", label: "trajectories", columns: pairs }];
}

const SOLOW_SERIES = [
  "capital",
  "output",
  "consumption",
  "investment",
  "savings_rate",
  "output_per_worker_index",
  "output_per_worker_growth",
] as const;

export function solowTables(r: SolowResponse): Table[] {
  const u = r.units;
  const columns: Column[] = [col("year", r.years, u, "years")];
  for (const path of ["baseline", "scenario"] as const) {
    for (const key of SOLOW_SERIES) columns.push(col(`${path}_${key}`, r[path][key], u, key));
  }
  return [{ name: "paths", label: "baseline and scenario paths", columns }];
}

/** Per-column statistics only. Never the file's rows: no preview, examples or top values. */
export function profileTables(r: ProfileResponse): Table[] {
  const cs = r.columns;
  const c = (name: string, pick: (x: (typeof cs)[number]) => Cell): Column => ({
    name,
    values: cs.map(pick),
  });
  return [
    {
      name: "column_statistics",
      label: "column statistics",
      columns: [
        c("index", (x) => x.index),
        c("name", (x) => x.name),
        c("type", (x) => x.type),
        c("inferred_type", (x) => x.inferred_type),
        c("overridden", (x) => x.overridden),
        c("missing_count", (x) => x.missing_count),
        c("missing_percent", (x) => x.missing_percent),
        c("invalid_count", (x) => x.invalid_count),
        c("invalid_percent", (x) => x.invalid_percent),
        c("valid_count", (x) => x.valid_count),
        c("numeric_count", (x) => x.numeric?.count),
        c("mean", (x) => x.numeric?.mean),
        c("std", (x) => x.numeric?.std),
        c("min", (x) => x.numeric?.min),
        c("q1", (x) => x.numeric?.q1),
        c("median", (x) => x.numeric?.median),
        c("q3", (x) => x.numeric?.q3),
        c("max", (x) => x.numeric?.max),
        c("categorical_count", (x) => x.categorical?.count),
        c("categorical_unique", (x) => x.categorical?.unique),
        c("categorical_other_count", (x) => x.categorical?.other_count),
        c("date_count", (x) => x.date?.count),
        c("date_unique", (x) => x.date?.unique),
        c("date_min", (x) => x.date?.min),
        c("date_max", (x) => x.date?.max),
        c("date_span_days", (x) => x.date?.span_days),
      ],
    },
  ];
}

export type ExportableResponse =
  | ProjectileResponse
  | QuadraticDragResponse
  | AngleSweepResponse
  | QuadraticAngleSweepResponse
  | IntegratorStudyResponse
  | SolowResponse
  | ProfileResponse;

/** The CSV tables for any model's response, chosen by its model id ([] if unknown). */
export function exportTables(response: ExportableResponse): Table[] {
  switch (response.model.id) {
    case "physics.projectile":
      return projectileTables(response as ProjectileResponse);
    case "physics.projectile.quadratic_drag":
      return quadraticDragTables(response as QuadraticDragResponse);
    case "physics.projectile.angle_sweep":
      return angleSweepTables(response as AngleSweepResponse);
    case "physics.projectile.quadratic_angle_sweep":
      return quadraticAngleSweepTables(response as QuadraticAngleSweepResponse);
    case "physics.projectile.integrators":
      return integratorTables(response as IntegratorStudyResponse);
    case "economy.solow":
      return solowTables(response as SolowResponse);
    case "quant.dataset_profile":
      return profileTables(response as ProfileResponse);
    default:
      return [];
  }
}
