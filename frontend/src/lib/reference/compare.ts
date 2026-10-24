/**
 * The reference run's comparison table (roadmap 1.6, D8 option b): which inputs differ, and
 * how each headline summary value moved from the reference run to this run.
 *
 * Both lists are read from the two responses on screen. Their field names are those a run
 * record stores (`inputs=` and `summary=` in backend/src/simforge/api/routes/), flattened with
 * dots as `flatten` in backend/src/simforge/api/replay.py does, so a row here names the same
 * field as the experiment log and a replay. The changes are plain arithmetic on the values
 * as computed: no verdict. Replay tolerances say whether a *recomputation* reproduced a run;
 * they say nothing about whether a change between two different scenarios matters.
 */

import type { ModelResponse } from "@/lib/api/client";
import { isModelResponse } from "@/lib/api/models";

/** A flattened record: dotted field name → value (numbers, text, booleans, null or a list). */
export type Fields = Record<string, unknown>;

/** Nested objects become dotted names; lists and other values are kept whole (as `flatten`). */
function flatten(d: Record<string, unknown>, prefix = ""): Fields {
  const out: Fields = {};
  for (const [key, value] of Object.entries(d)) {
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      Object.assign(out, flatten(value as Record<string, unknown>, `${prefix}${key}.`));
    } else {
      out[`${prefix}${key}`] = value;
    }
  }
  return out;
}

/**
 * Categorical and mixed: the non-missing values come from at least two of three groups
 * (number-like, date, other text). The backend's `is_mixed` in quant/profiling/model.py.
 */
function isMixed(c: {
  inferred_type: string;
  kind_counts: {
    number: number;
    leading_zero_number: number;
    non_finite_number: number;
    date: number;
    ambiguous_date: number;
    text: number;
  };
}): boolean {
  const k = c.kind_counts;
  const groups = [
    k.number + k.leading_zero_number,
    k.date,
    k.non_finite_number + k.ambiguous_date + k.text,
  ];
  return c.inferred_type === "categorical" && groups.filter((g) => g > 0).length >= 2;
}

/** A copy of `d` without the field `key`. */
function without<T extends object>(d: T, key: keyof T): Partial<T> {
  return Object.fromEntries(Object.entries(d).filter(([k]) => k !== key)) as Partial<T>;
}

/** The inputs a run record stores for this response's model, read from what it echoes. */
export function inputFields(r: ModelResponse): Fields {
  if (isModelResponse(r, "physics.projectile")) {
    // The time grid is linspace(0, flight_time, n_samples), so it has n_samples points.
    return flatten({ parameters: r.parameters, solver: r.solver, n_samples: r.series.t.length });
  }
  if (isModelResponse(r, "physics.projectile.angle_sweep")) {
    // A sweep does not use the launch angle; angles_deg is linspace(0, 90, n_angles).
    return flatten({
      parameters: without(r.parameters, "launch_angle_deg"),
      n_angles: r.angles_deg.length,
    });
  }
  if (isModelResponse(r, "physics.projectile.integrators")) {
    return flatten({ parameters: r.parameters, dt_values: r.dt_values, methods: r.methods });
  }
  if (isModelResponse(r, "economy.solow")) {
    return flatten({ parameters: r.parameters, policy: r.policy, horizon_years: r.horizon_years });
  }
  if (isModelResponse(r, "quant.dataset_profile")) {
    // The file is identified by its bytes (hash and size), never its name or rows.
    return flatten({
      dataset: { sha256: r.dataset.sha256, byte_size: r.dataset.byte_size },
      options: r.options,
    });
  }
  return {};
}

/** The headline summary a run record stores for this response's model, flattened. */
export function summaryFields(r: ModelResponse): Fields {
  if (isModelResponse(r, "physics.projectile")) {
    return flatten({
      analytical: without(r.analytical, "method_note"),
      numerical: r.numerical,
      comparison: r.comparison,
    });
  }
  if (isModelResponse(r, "physics.projectile.angle_sweep")) {
    return {
      best_angle_deg: r.best_angle_deg,
      best_range: r.best_range,
      vacuum_best_angle_deg: r.vacuum_best_angle_deg,
      vacuum_best_range: r.vacuum_best_range,
    };
  }
  if (isModelResponse(r, "physics.projectile.integrators")) {
    const methods = Object.fromEntries(
      r.results.map((m) => [
        m.method,
        {
          theoretical_order: m.theoretical_order,
          position_order: m.position_fit ? m.position_fit.order : null,
          position_fit_points: m.position_fit ? m.position_fit.n_points : 0,
          velocity_order: m.velocity_fit ? m.velocity_fit.order : null,
          finest_max_position_error: m.runs.at(-1)?.max_position_error ?? null,
        },
      ]),
    );
    return flatten({ horizon: r.horizon, methods });
  }
  if (isModelResponse(r, "economy.solow")) {
    return {
      baseline_steady_state_capital: r.baseline_steady_state.capital,
      scenario_steady_state_capital: r.scenario_steady_state.capital,
      golden_rule_savings_rate: r.golden_rule.savings_rate,
      half_life_years: r.convergence.half_life_years,
      final_capital: r.scenario.capital.at(-1),
    };
  }
  if (isModelResponse(r, "quant.dataset_profile")) {
    return {
      source: r.dataset.source,
      sample_id: r.dataset.sample_id,
      rows: r.n_rows,
      columns: r.n_columns,
      missing_cells: r.missing_cells,
      duplicate_rows: r.duplicates.duplicate_rows,
      mixed_columns: r.columns.filter(isMixed).length,
    };
  }
  return {};
}

const isNumber = (x: unknown): x is number => typeof x === "number";
/** Equal as stored values: same type and value, lists element by element. */
const same = (a: unknown, b: unknown) => JSON.stringify(a) === JSON.stringify(b);

/** One input that differs between the reference run and this run. */
export interface InputChange {
  field: string;
  reference: unknown;
  current: unknown;
}

/** One summary value: arithmetic for two numbers, otherwise only equal or changed. */
export type SummaryRow =
  | {
      field: string;
      kind: "number";
      reference: number;
      current: number;
      /** current − reference. */
      absolute: number;
      /** (current − reference) / |reference|; null (undefined) when the reference is 0. */
      relative: number | null;
    }
  | {
      field: string;
      kind: "other";
      /** undefined when the field exists in only one of the two runs. */
      reference: unknown;
      current: unknown;
      equal: boolean;
    };

/** Fields of both runs: the reference's in order, then any only the current run has. */
function fieldNames(a: Fields, b: Fields): string[] {
  return [...Object.keys(a), ...Object.keys(b).filter((k) => !(k in a))];
}

/** The inputs that differ (only those), with both values. */
export function inputDiff(reference: ModelResponse, current: ModelResponse): InputChange[] {
  const [a, b] = [inputFields(reference), inputFields(current)];
  return fieldNames(a, b)
    .filter((f) => !(f in a && f in b && same(a[f], b[f])))
    .map((field) => ({ field, reference: a[field], current: b[field] }));
}

/** Every headline summary field, with its change from the reference run to this run. */
export function summaryDiff(reference: ModelResponse, current: ModelResponse): SummaryRow[] {
  const [a, b] = [summaryFields(reference), summaryFields(current)];
  return fieldNames(a, b).map((field): SummaryRow => {
    const [ref, cur] = [a[field], b[field]];
    if (isNumber(ref) && isNumber(cur)) {
      const absolute = cur - ref;
      return {
        field,
        kind: "number",
        reference: ref,
        current: cur,
        absolute,
        relative: ref === 0 ? null : absolute / Math.abs(ref),
      };
    }
    const equal = field in a && field in b && same(ref, cur);
    return { field, kind: "other", reference: ref, current: cur, equal };
  });
}

/**
 * True when there is at least one numeric field and every one is exactly unchanged: no
 * numeric change, and no field that is a number in one run but missing or null in the other.
 */
export function allNumbersEqual(rows: readonly SummaryRow[]): boolean {
  const numbers = rows.filter((r) => r.kind === "number");
  const halfNumeric = rows.some(
    (r) => r.kind === "other" && !r.equal && (isNumber(r.reference) || isNumber(r.current)),
  );
  return numbers.length > 0 && !halfNumeric && numbers.every((r) => r.absolute === 0);
}

/** The comparison of two runs of the same model, or null for two different models. */
export function compareRuns(
  reference: ModelResponse,
  current: ModelResponse,
): { inputs: InputChange[]; summary: SummaryRow[] } | null {
  if (reference.model.id !== current.model.id) return null;
  return { inputs: inputDiff(reference, current), summary: summaryDiff(reference, current) };
}
