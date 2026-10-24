/**
 * CSV export made in the browser from the response already on screen (roadmap 1.6, D3/D4).
 *
 * Format: RFC 4180 (comma separator, CRLF line endings, a field containing a comma, quote,
 * CR or LF is quoted and its quotes doubled). One header line, `name [unit]` when the unit is
 * known, then one line per row. No comment lines: provenance lives in the filename and in
 * the JSON export.
 */

export type Cell = number | string | boolean | null | undefined;

/** One quantity: its name, its unit (if known) and its values, row by row. */
export type Column = { name: string; unit?: string; values: readonly Cell[] };

/** A wide table. `name` goes in the filename; `label` is what the download button says. */
export type Table = { name: string; label: string; columns: Column[] };

const NEEDS_QUOTES = /[",\r\n]/;
// Text starting with one of these can be run as a formula by a spreadsheet.
const FORMULA_START = /^[=+\-@\t\r]/;

/** A number written as the shortest string that parses back to exactly the same double. */
function formatNumber(x: number): string {
  if (!Number.isFinite(x)) throw new Error(`Cannot export a non-finite number (${x})`);
  // String(-0) is "0", which would lose the sign; "-0" parses back to -0.
  return Object.is(x, -0) ? "-0" : String(x);
}

/** Text with a leading `'` if a spreadsheet could read it as a formula, then quoted. */
function formatText(s: string): string {
  const safe = FORMULA_START.test(s) ? `'${s}` : s;
  return NEEDS_QUOTES.test(safe) ? `"${safe.replaceAll('"', '""')}"` : safe;
}

function formatCell(cell: Cell): string {
  if (cell === null || cell === undefined) return "";
  if (typeof cell === "number") return formatNumber(cell);
  if (typeof cell === "boolean") return cell ? "true" : "false";
  return formatText(cell);
}

/** The table as CSV text. Shorter columns are padded at the end with empty cells. */
export function toCsv(table: Table): string {
  const { columns } = table;
  const header = columns.map((c) => formatText(c.unit ? `${c.name} [${c.unit}]` : c.name));
  const lines = [header.join(",")];
  const rows = Math.max(0, ...columns.map((c) => c.values.length));
  for (let i = 0; i < rows; i++) {
    lines.push(columns.map((c) => formatCell(c.values[i])).join(","));
  }
  return lines.map((line) => `${line}\r\n`).join("");
}

/** `<model_id>_<first 8 characters of the run id>_<table>.csv`. User labels never appear. */
export function csvFilename(modelId: string, runId: string, table: string): string {
  return `${modelId}_${runId.slice(0, 8)}_${table}.csv`;
}
