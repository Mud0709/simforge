"use client";

import { useMemo } from "react";

import type { ModelResponse } from "@/lib/api/client";
import { formatSig } from "@/lib/format";
import { type SummaryRow, allNumbersEqual, compareRuns } from "@/lib/reference/compare";

/** A stored value as shown: numbers to 6 significant figures, lists joined, null as "none". */
function shown(value: unknown): string {
  if (value === undefined) return "absent";
  if (value === null) return "none";
  if (typeof value === "number") return formatSig(value);
  if (Array.isArray(value))
    return value.every((v) => typeof v !== "object" || v === null)
      ? value.map(shown).join(", ")
      : JSON.stringify(value);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

/**
 * A change with its sign: "+1", "-0.2", or "0" for no change (also -0). A change that
 * overflows a double (e.g. a ratio to a tiny reference) is "—", never "Infinity" or "+—".
 */
const signed = (x: number) => (x > 0 && Number.isFinite(x) ? `+${formatSig(x)}` : formatSig(x));

/** True when a numeric row's change cannot be shown as a finite number (overflow). */
const overflows = (row: SummaryRow) =>
  row.kind === "number" &&
  (!Number.isFinite(row.absolute) ||
    (row.relative !== null && !Number.isFinite(row.relative * 100)));

function changeCells(row: SummaryRow) {
  if (row.kind === "other") return [row.equal ? "equal" : "changed", ""];
  // The relative change is undefined when the reference is 0: shown as "—", never Infinity.
  const percent = row.relative === null ? null : row.relative * 100;
  const relative = percent === null || !Number.isFinite(percent) ? "—" : `${signed(percent)}%`;
  return [signed(row.absolute), relative];
}

/**
 * How this run differs from the reference run (roadmap 1.6, D8): the inputs that changed,
 * and each headline summary value with its absolute and relative change. Shown only for two
 * different runs of the same model. It states differences only: whether a difference
 * matters is a scientific question the table cannot answer, so it gives no verdict.
 */
export function ComparisonTable({
  reference,
  current,
}: {
  reference: ModelResponse;
  current: ModelResponse;
}) {
  const comparison = useMemo(() => compareRuns(reference, current), [reference, current]);
  if (!comparison || reference.metadata.run_id === current.metadata.run_id) return null;
  const { inputs, summary } = comparison;
  const undefinedRelative = summary.some((r) => r.kind === "number" && r.relative === null);
  const overflow = summary.some(overflows);

  return (
    <div className="comparison" data-testid="comparison">
      {inputs.length === 0 ? (
        <p className="note">No input differs from the reference run.</p>
      ) : (
        <table aria-label="Inputs that differ from the reference run">
          <thead>
            <tr>
              <th scope="col">Input</th>
              <th scope="col">Reference run</th>
              <th scope="col">This run</th>
            </tr>
          </thead>
          <tbody>
            {inputs.map((c) => (
              <tr key={c.field}>
                <th scope="row">
                  <code>{c.field}</code>
                </th>
                <td>{shown(c.reference)}</td>
                <td>{shown(c.current)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <table aria-label="Summary: reference run and this run">
        <thead>
          <tr>
            <th scope="col">Summary value</th>
            <th scope="col">Reference run</th>
            <th scope="col">This run</th>
            <th scope="col">Change (this − reference)</th>
            <th scope="col">Relative change</th>
          </tr>
        </thead>
        <tbody>
          {summary.map((row) => (
            <tr key={row.field}>
              <th scope="row">
                <code>{row.field}</code>
              </th>
              <td>{shown(row.reference)}</td>
              <td>{shown(row.current)}</td>
              {changeCells(row).map((text, i) => (
                <td key={i}>{text}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="note">
        Relative change = (this − reference) / |reference|. Values are rounded to 6 significant
        figures for display; the changes are worked out from the full values.
        {undefinedRelative &&
          " Where the reference value is 0, the relative change is undefined (—)."}
        {overflow && " A change too large to represent as a number is shown as —."}
      </p>
      {allNumbersEqual(summary) && (
        <p className="note" role="note">
          Every numeric summary value is exactly equal to the reference run&rsquo;s.
        </p>
      )}
    </div>
  );
}
