"use client";

import { type FormEvent, useEffect, useRef, useState } from "react";

import {
  ApiError,
  type ColumnType,
  type Delimiter,
  type ProfileRequest,
  type ProfileResponse,
  type SampleId,
  type SampleInfo,
  listSampleDatasets,
  profileDataset,
} from "@/lib/api/client";
import { fileSizeProblem, fileToBase64, parseMarkers } from "@/lib/quant/upload";
import { QuantAssumptions, QuantCharts, QuantSummary, QuantValidation } from "./QuantResults";
import { Workspace } from "./Workspace";

/** The chosen file could not be read (moved, deleted or changed since it was chosen). */
class FileReadError extends Error {
  constructor() {
    super("Could not read the file. It may have been moved or changed; choose it again.");
  }
}

/** Mirrors the server's default missing-value markers (which remain the authority). */
const DEFAULT_MARKERS = "NA, N/A, NaN, None, null";

type Overrides = Record<number, ColumnType>;

/**
 * Everything that determines a profile, as one string. A result is shown as current only
 * while this matches the key it was computed with, so changed settings never pass as fresh.
 */
function settingsKey(
  source: string,
  delimiter: Delimiter,
  markers: string[],
  overrides: Overrides,
): string {
  const canonicalMarkers = [...new Set(markers)].sort();
  const canonicalOverrides = Object.entries(overrides)
    .map(([c, t]) => [Number(c), t] as const)
    .sort((a, b) => a[0] - b[0]);
  return JSON.stringify([source, delimiter, canonicalMarkers, canonicalOverrides]);
}

export function QuantLab() {
  const [sourceKind, setSourceKind] = useState<"upload" | "sample">("sample");
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [sampleId, setSampleId] = useState<SampleId>("messy_survey");
  const [file, setFile] = useState<File | null>(null);
  const [fileVersion, setFileVersion] = useState(0);
  const [delimiter, setDelimiter] = useState<Delimiter>("comma");
  const [markersText, setMarkersText] = useState(DEFAULT_MARKERS);
  const [overrides, setOverrides] = useState<Overrides>({});
  const [save, setSave] = useState(false);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProfileResponse | null>(null);
  const [resultKey, setResultKey] = useState<string | null>(null);
  const [resultSource, setResultSource] = useState<string | null>(null);
  const latestRequest = useRef(0);

  useEffect(() => {
    listSampleDatasets()
      .then(setSamples)
      .catch(() => setSamples([]));
  }, []);

  const source = sourceKind === "sample" ? `sample:${sampleId}` : `file:${fileVersion}`;
  const markers = parseMarkers(markersText);
  const currentKey = settingsKey(source, delimiter, markers, overrides);
  const stale = result !== null && resultKey !== currentKey;
  // Overrides refer to column positions of the profiled table, so they only make sense while
  // the same file (or sample) is read with the same delimiter: a different delimiter splits
  // the rows into different columns.
  const sameTable =
    result !== null && resultSource === source && result.options.delimiter === delimiter;

  /** Anything that changes which columns exist also discards the overrides. */
  function changeSource(next: () => void) {
    next();
    setOverrides({});
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (sourceKind === "upload") {
      if (!file) {
        setError("Choose a CSV file first.");
        return;
      }
      const tooBig = fileSizeProblem(file.size);
      if (tooBig) {
        setError(tooBig);
        return;
      }
    }
    // Claim the request number and disable the button *before* reading the file, so a
    // second click during a slow read is ignored and replies are ordered by click.
    const id = ++latestRequest.current;
    const key = currentKey;
    const requestSource = source;
    setStatus("running");
    try {
      let content_base64 = "";
      if (sourceKind === "upload" && file) {
        try {
          content_base64 = await fileToBase64(file);
        } catch {
          throw new FileReadError();
        }
      }
      const body: ProfileRequest = {
        source:
          sourceKind === "upload"
            ? { kind: "upload", content_base64 }
            : { kind: "sample", sample_id: sampleId },
        options: {
          delimiter,
          missing_markers: markers,
          column_types: Object.entries(overrides).map(([column, type]) => ({
            column: Number(column),
            type,
          })),
        },
        save_experiment: save,
      };
      const response = await profileDataset(body);
      if (id !== latestRequest.current) return; // a newer request has started
      setResult(response);
      setResultKey(key);
      setResultSource(requestSource);
    } catch (err) {
      if (id !== latestRequest.current) return;
      setError(
        err instanceof ApiError || err instanceof FileReadError ? err.message : "Unexpected error",
      );
    } finally {
      if (id === latestRequest.current) setStatus("idle");
    }
  }

  const form = (
    <form onSubmit={onSubmit} noValidate aria-label="Dataset import settings">
      <fieldset>
        <legend>Data</legend>
        <label className="checkbox">
          <input
            type="radio"
            name="source"
            checked={sourceKind === "sample"}
            onChange={() => changeSource(() => setSourceKind("sample"))}
          />
          Bundled sample
        </label>
        <label className="checkbox">
          <input
            type="radio"
            name="source"
            checked={sourceKind === "upload"}
            onChange={() => changeSource(() => setSourceKind("upload"))}
          />
          Upload a CSV file
        </label>
        {sourceKind === "sample" ? (
          <div className="field">
            <label htmlFor="sample">Sample dataset</label>
            <select
              id="sample"
              value={sampleId}
              onChange={(e) => changeSource(() => setSampleId(e.target.value as SampleId))}
            >
              {(samples.length
                ? samples
                : [{ id: "messy_survey", title: "Survey (deliberately messy)", description: "" }]
              ).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.title}
                </option>
              ))}
            </select>
            <p className="note">
              Invented data. {samples.find((s) => s.id === sampleId)?.description}
            </p>
          </div>
        ) : (
          <div className="field">
            <label htmlFor="file">CSV file (UTF-8, at most 2 MiB)</label>
            <input
              id="file"
              type="file"
              accept=".csv,text/csv,text/plain"
              onChange={(e) =>
                changeSource(() => {
                  setFile(e.target.files?.[0] ?? null);
                  setFileVersion((v) => v + 1);
                })
              }
            />
            <p className="note">
              The file is sent for this profile only and is not stored on the server. It stays in
              this browser tab until you reload or choose another file.
            </p>
          </div>
        )}
      </fieldset>
      <fieldset>
        <legend>Reading the file</legend>
        <div className="field">
          <label htmlFor="delimiter">Delimiter</label>
          <select
            id="delimiter"
            value={delimiter}
            onChange={(e) => changeSource(() => setDelimiter(e.target.value as Delimiter))}
          >
            <option value="comma">Comma ( , )</option>
            <option value="semicolon">Semicolon ( ; )</option>
            <option value="tab">Tab</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="markers">Missing-value markers</label>
          <input
            id="markers"
            type="text"
            value={markersText}
            onChange={(e) => setMarkersText(e.target.value)}
            aria-describedby="markers-help"
          />
          <p className="note" id="markers-help">
            Comma-separated, case-sensitive. Empty cells are always missing. Remove NA if it means
            something in your data (it is Namibia&rsquo;s country code).
          </p>
        </div>
      </fieldset>
      {sameTable && result && (
        <fieldset>
          <legend>Column types</legend>
          <p className="note">
            Change a type if the inference is wrong. Values that do not fit are counted as invalid,
            never converted.
          </p>
          {result.columns.map((c) => (
            <div className="field" key={c.index}>
              <label htmlFor={`type-${c.index}`}>{c.name}</label>
              <select
                id={`type-${c.index}`}
                value={overrides[c.index] ?? ""}
                onChange={(e) => {
                  const value = e.target.value as ColumnType | "";
                  setOverrides((prev) => {
                    const next = { ...prev };
                    if (value === "") delete next[c.index];
                    else next[c.index] = value;
                    return next;
                  });
                }}
              >
                <option value="">As inferred ({c.inferred_type})</option>
                <option value="numeric">numeric</option>
                <option value="date">date</option>
                <option value="categorical">categorical</option>
              </select>
            </div>
          ))}
        </fieldset>
      )}
      <label className="checkbox">
        <input type="checkbox" checked={save} onChange={(e) => setSave(e.target.checked)} />
        Save to the experiment log (the file&rsquo;s hash, size, settings and counts only)
      </label>
      <button type="submit" disabled={status === "running"}>
        {status === "running" ? "Profiling…" : result ? "Profile again" : "Profile dataset"}
      </button>
      {error && (
        <p className="api-error" role="alert">
          {error}
        </p>
      )}
    </form>
  );

  const empty = (text: string) => <p className="empty">{text}</p>;
  const staleBanner = stale && (
    <p className="api-error stale" role="status">
      The settings or the data have changed since this profile was made. Press &ldquo;Profile
      again&rdquo; to update it; the results below are for the previous settings.
    </p>
  );

  return (
    <Workspace
      parameters={form}
      visualisation={
        result ? (
          <>
            {staleBanner}
            <QuantCharts key={result.metadata.run_id} result={result} />
          </>
        ) : (
          empty("Profile a dataset to see where values are missing and how each column is spread.")
        )
      }
      results={
        result ? (
          <>
            {staleBanner}
            <QuantSummary result={result} />
          </>
        ) : (
          empty(
            "Row and column counts, types, missing values, duplicates and summaries appear here.",
          )
        )
      }
      assumptions={
        result ? (
          <QuantAssumptions result={result} />
        ) : (
          empty("How each cell is interpreted is listed with every profile.")
        )
      }
      validation={
        result ? (
          <QuantValidation result={result} />
        ) : (
          empty("Each profile reports its own accounting checks and the dataset's identity here.")
        )
      }
    />
  );
}
