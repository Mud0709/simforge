import type { ValidationCheck } from "@/lib/api/client";
import { formatExp } from "@/lib/format";

const KIND_LABEL: Record<ValidationCheck["kind"], string> = {
  exact_identity: "Exact identity",
  numerical_diagnostic: "Numerical diagnostic",
  informational: "Information",
};

function status(c: ValidationCheck) {
  if (c.passed === true) return <span className="check-status pass">Pass</span>;
  if (c.passed === false) return <span className="check-status fail">Fail</span>;
  return <span className="check-status">Info</span>;
}

/** Whole numbers (counts, such as a number of mismatches) as integers; the rest in e-notation. */
const defaultFormat = (v: number) =>
  Number.isInteger(v) && Math.abs(v) < 1e6 ? String(v) : formatExp(v);

/**
 * Per-run checks, as returned by any model (shared by the Economy and Quant labs). Each row
 * shows the check's kind, its value, its limit and whether it passed; hover for the note.
 */
export function ChecksTable({
  checks,
  format = defaultFormat,
}: {
  checks: ValidationCheck[];
  /** How values and limits are written; counts read better as plain integers. */
  format?: (value: number) => string;
}) {
  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            <th scope="col">Check</th>
            <th scope="col">Value</th>
            <th scope="col">Limit</th>
            <th scope="col">Status</th>
          </tr>
        </thead>
        <tbody>
          {checks.map((c) => (
            <tr key={c.id} title={c.note} data-testid={`check-${c.id}`}>
              <th scope="row" className="check-label">
                {c.label}
                <span className="check-kind">{KIND_LABEL[c.kind]}</span>
              </th>
              <td className="num">{format(c.value)}</td>
              <td className="num">
                {c.threshold === null || c.threshold === undefined ? "—" : format(c.threshold)}
              </td>
              <td>{status(c)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
