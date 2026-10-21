"use client";

import type { Data } from "plotly.js";
import { useMemo, useState } from "react";

import type { ColumnProfile, ProfileResponse } from "@/lib/api/client";
import { formatSig } from "@/lib/format";
import { binGeometry } from "@/lib/quant/histogram";
import { ChecksTable } from "./ChecksTable";
import { PlotlyChart } from "./PlotlyChart";

const MISSING = "#64748b";
const INVALID = "#ea580c";
const BARS = "#2563eb";

type Props = { result: ProfileResponse };

const percent = (x: number) => `${x.toFixed(1)}%`;
const integer = (x: number) => x.toLocaleString("en-GB");
const num = (x: number | null | undefined) => (x === null || x === undefined ? "—" : formatSig(x));

const DELIMITER_LABEL = { comma: "comma", semicolon: "semicolon", tab: "tab" } as const;

function typeLabel(c: ColumnProfile): string {
  return c.overridden ? `${c.type} (set by you; inferred ${c.inferred_type})` : c.type;
}

function defaultColumn(columns: ColumnProfile[]): number {
  return (columns.find((c) => c.numeric) ?? columns.find((c) => c.categorical) ?? columns[0])!
    .index;
}

function DistributionChart({ column }: { column: ColumnProfile }) {
  const data = useMemo<Data[] | null>(() => {
    if (column.numeric) {
      const { edges, counts } = column.numeric.histogram;
      const { centres: x, widths } = binGeometry(edges);
      return [
        {
          type: "bar",
          x,
          y: counts,
          width: widths,
          marker: { color: BARS },
          hovertemplate: "%{y} values<extra></extra>",
        },
      ];
    }
    if (column.categorical) {
      const top = column.categorical.top;
      const labels = top.map((t) => t.value);
      const counts = top.map((t) => t.count);
      if (column.categorical.other_count > 0) {
        labels.push("(all other values)");
        counts.push(column.categorical.other_count);
      }
      return [{ type: "bar", x: labels, y: counts, marker: { color: BARS } }];
    }
    return null;
  }, [column]);

  if (!data) {
    return (
      <p className="note">
        {column.date
          ? "Dates are summarised in the Results table; a time chart is not drawn in this version."
          : "This column has no valid values to plot."}
      </p>
    );
  }
  const xTitle = column.numeric ? `${column.name} (histogram bins)` : column.name;
  return (
    <PlotlyChart
      title={`Distribution of ${column.name}`}
      data={data}
      layout={{
        xaxis: { title: { text: xTitle }, automargin: true },
        yaxis: { title: { text: "count" } },
        showlegend: false,
        bargap: column.numeric ? 0 : 0.2,
      }}
    />
  );
}

/** Visualisation: where values are missing or invalid, and the distribution of one column. */
export function QuantCharts({ result }: Props) {
  const [chosen, setChosen] = useState<number>(() => defaultColumn(result.columns));
  const column = result.columns.find((c) => c.index === chosen) ?? result.columns[0]!;
  const names = result.columns.map((c) => c.name);
  return (
    <>
      <h3>Missing and invalid values by column</h3>
      <PlotlyChart
        title="Missing and invalid values by column, as a percentage of rows"
        data={[
          {
            type: "bar",
            name: "missing",
            x: names,
            y: result.columns.map((c) => c.missing_percent),
            marker: { color: MISSING },
          },
          {
            type: "bar",
            name: "invalid for the chosen type",
            x: names,
            y: result.columns.map((c) => c.invalid_percent),
            marker: { color: INVALID },
          },
        ]}
        layout={{
          barmode: "stack",
          yaxis: { title: { text: "% of rows" }, rangemode: "tozero" },
          xaxis: { automargin: true },
        }}
        height={300}
      />
      <h3>Distribution of one column</h3>
      <div className="field">
        <label htmlFor="plot-column">Column to plot</label>
        <select
          id="plot-column"
          value={column.index}
          onChange={(e) => setChosen(Number(e.target.value))}
        >
          {result.columns.map((c) => (
            <option key={c.index} value={c.index}>
              {c.name} ({c.type})
            </option>
          ))}
        </select>
      </div>
      <DistributionChart column={column} />
    </>
  );
}

/** Results: the dataset's shape and quality, then per-type summaries and a preview. */
export function QuantSummary({ result }: Props) {
  const cells = result.n_rows * result.n_columns;
  const numeric = result.columns.filter((c) => c.numeric);
  const categorical = result.columns.filter((c) => c.categorical);
  const dates = result.columns.filter((c) => c.date);
  const flagged = result.columns.filter(
    (c) => c.notes.length > 0 || c.invalid_count > 0 || c.missing_count > 0,
  );
  const dup = result.duplicates;
  return (
    <>
      <p className="note">
        Descriptive summary of the rows in this file only: no estimates, tests or predictions.
      </p>
      <dl className="stats">
        <div>
          <dt>Rows</dt>
          <dd data-testid="profile-rows">{integer(result.n_rows)}</dd>
        </div>
        <div>
          <dt>Columns</dt>
          <dd data-testid="profile-columns">{integer(result.n_columns)}</dd>
        </div>
        <div>
          <dt>Missing cells</dt>
          <dd data-testid="profile-missing">
            {integer(result.missing_cells)} of {integer(cells)} (
            {percent((100 * result.missing_cells) / cells)})
          </dd>
        </div>
        <div>
          <dt>Duplicate rows</dt>
          <dd data-testid="profile-duplicates">{integer(dup.duplicate_rows)}</dd>
        </div>
        <div>
          <dt>Blank lines skipped</dt>
          <dd>{integer(result.blank_lines_skipped)}</dd>
        </div>
      </dl>
      {dup.duplicate_rows > 0 && (
        <p className="note">
          Identical rows (counted, not removed):{" "}
          {dup.examples.map((g) => `rows ${g.join(", ")}`).join("; ")}
          {dup.groups > dup.examples.length ? "; …" : ""}.
        </p>
      )}

      <h3>Columns</h3>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Column</th>
              <th scope="col">Type</th>
              <th scope="col">Missing</th>
              <th scope="col">Invalid</th>
              <th scope="col">Valid</th>
              <th scope="col">How the type was decided</th>
            </tr>
          </thead>
          <tbody>
            {result.columns.map((c) => (
              <tr key={c.index} data-testid={`column-${c.index}`}>
                <th scope="row">{c.name}</th>
                <td>{typeLabel(c)}</td>
                <td className="num">
                  {integer(c.missing_count)} ({percent(c.missing_percent)})
                </td>
                <td className="num">{integer(c.invalid_count)}</td>
                <td className="num">{integer(c.valid_count)}</td>
                <td className="reason">{c.inference_reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {flagged.length > 0 && (
        <>
          <h3>Things to check</h3>
          <ul className="assumptions" data-testid="column-notes">
            {flagged.map((c) => (
              <li key={c.index}>
                <strong>{c.name}</strong>
                {c.notes.length > 0 && `: ${c.notes.join(" ")}`}
                {Object.keys(c.missing_markers_found).length > 0 &&
                  ` Missing values found as: ${Object.entries(c.missing_markers_found)
                    .map(([m, n]) => `${m === "" ? "(empty)" : `'${m}'`} ×${n}`)
                    .join(", ")}.`}
                {c.invalid_examples.length > 0 &&
                  ` Invalid: ${c.invalid_examples.map((e) => `row ${e.row} '${e.value}'`).join(", ")}${c.invalid_count > c.invalid_examples.length ? ", …" : ""}.`}
              </li>
            ))}
          </ul>
        </>
      )}

      {numeric.length > 0 && (
        <>
          <h3>Numeric columns</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Column</th>
                  <th scope="col">n</th>
                  <th scope="col">Mean</th>
                  <th scope="col">SD (n − 1)</th>
                  <th scope="col">Min</th>
                  <th scope="col">Q1</th>
                  <th scope="col">Median</th>
                  <th scope="col">Q3</th>
                  <th scope="col">Max</th>
                </tr>
              </thead>
              <tbody>
                {numeric.map((c) => {
                  const s = c.numeric!;
                  return (
                    <tr key={c.index} data-testid={`numeric-${c.index}`}>
                      <th scope="row">{c.name}</th>
                      <td className="num">{integer(s.count)}</td>
                      <td className="num">{num(s.mean)}</td>
                      <td className="num">{num(s.std)}</td>
                      <td className="num">{num(s.min)}</td>
                      <td className="num">{num(s.q1)}</td>
                      <td className="num">{num(s.median)}</td>
                      <td className="num">{num(s.q3)}</td>
                      <td className="num">{num(s.max)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="note">
            Shown to 6 significant figures. Quartiles use linear interpolation (type 7), which can
            differ from the &ldquo;median of each half&rdquo; method for small samples. — means not
            defined (fewer than two values) or not representable.
          </p>
        </>
      )}

      {categorical.length > 0 && (
        <>
          <h3>Categorical columns</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Column</th>
                  <th scope="col">n</th>
                  <th scope="col">Distinct</th>
                  <th scope="col">Most frequent (count)</th>
                  <th scope="col">Other</th>
                </tr>
              </thead>
              <tbody>
                {categorical.map((c) => {
                  const s = c.categorical!;
                  return (
                    <tr key={c.index} data-testid={`categorical-${c.index}`}>
                      <th scope="row">{c.name}</th>
                      <td className="num">{integer(s.count)}</td>
                      <td className="num">{integer(s.unique)}</td>
                      <td className="reason">
                        {s.top.map((t) => `${t.value} (${t.count})`).join(", ")}
                      </td>
                      <td className="num">{integer(s.other_count)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      {dates.length > 0 && (
        <>
          <h3>Date columns</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Column</th>
                  <th scope="col">n</th>
                  <th scope="col">Distinct</th>
                  <th scope="col">Earliest</th>
                  <th scope="col">Latest</th>
                  <th scope="col">Span (days)</th>
                </tr>
              </thead>
              <tbody>
                {dates.map((c) => {
                  const s = c.date!;
                  return (
                    <tr key={c.index} data-testid={`date-${c.index}`}>
                      <th scope="row">{c.name}</th>
                      <td className="num">{integer(s.count)}</td>
                      <td className="num">{integer(s.unique)}</td>
                      <td>{s.min}</td>
                      <td>{s.max}</td>
                      <td className="num">{num(s.span_days)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </>
      )}

      <h3>Preview</h3>
      <p className="note">
        The first {result.preview.rows.length} of {integer(result.n_rows)} rows, exactly as read
        (before any interpretation)
        {result.preview.truncated_cells > 0
          ? `; ${result.preview.truncated_cells} long cell(s) shortened for display`
          : ""}
        .
      </p>
      <div className="table-scroll preview">
        <table>
          <thead>
            <tr>
              <th scope="col">Row</th>
              {result.preview.columns.map((name, i) => (
                <th scope="col" key={i}>
                  {name}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {result.preview.rows.map((row, r) => (
              <tr key={r}>
                <th scope="row">{r + 1}</th>
                {row.map((cell, i) => (
                  <td key={i}>{cell === "" ? <span className="unit">(empty)</span> : cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

/** Assumptions: how cells were interpreted, and the settings used for this profile. */
export function QuantAssumptions({ result }: Props) {
  const o = result.options;
  return (
    <>
      <ul className="assumptions">
        {result.assumptions.map((a) => (
          <li key={a.id}>{a.statement}</li>
        ))}
      </ul>
      <h3>Settings used</h3>
      <p className="note">
        Delimiter: {DELIMITER_LABEL[o.delimiter ?? "comma"]}. Missing-value markers (besides empty
        cells):{" "}
        {o.missing_markers?.length ? o.missing_markers.map((m) => `'${m}'`).join(", ") : "none"}.
        Type overrides: {o.column_types?.length ?? 0}.
      </p>
      <h3>How it is computed</h3>
      <p className="note">{result.method_note}</p>
    </>
  );
}

/** Validation: exact accounting checks for this profile, and the dataset's identity. */
export function QuantValidation({ result }: Props) {
  const d = result.dataset;
  const m = result.metadata;
  return (
    <>
      <ChecksTable checks={result.checks} format={integer} />
      <p className="note">
        These checks confirm that every cell, row and value is counted exactly once. They check the
        bookkeeping of this profile, not whether the data themselves are correct.
      </p>
      <h3>Dataset identity</h3>
      <dl className="meta">
        <dt>Source</dt>
        <dd>{d.source === "sample" ? `bundled sample (${d.sample_id})` : "your upload"}</dd>
        <dt>Size</dt>
        <dd>
          {integer(d.byte_size)} bytes{d.had_bom ? " (with a UTF-8 byte-order mark)" : ""}
        </dd>
        <dt>SHA-256 of the bytes</dt>
        <dd>
          <code data-testid="dataset-sha256">{d.sha256}</code>
        </dd>
        <dt>Profile identity</dt>
        <dd>
          <code title="SHA-256 of the file hash, size and every setting">{m.input_hash}</code>
        </dd>
        <dt>Model</dt>
        <dd>
          {result.model.id} v{result.model.version}
        </dd>
        <dt>Run</dt>
        <dd>
          {m.created_at.slice(0, 19).replace("T", " ")} UTC, {formatSig(m.elapsed_ms, 3)} ms,
          {m.experiment_saved ? " saved to the experiment log" : " not saved"}
        </dd>
      </dl>
      <p className="note">
        The SHA-256 identifies these exact bytes: change one byte and it changes. It proves which
        file was profiled, not that its contents are accurate. The profile identity also covers
        every setting, so a changed setting can never be mistaken for this result. The file is not
        stored on the server.
      </p>
    </>
  );
}
