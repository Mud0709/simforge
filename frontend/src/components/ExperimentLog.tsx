"use client";

import { Fragment, useEffect, useState } from "react";

import {
  ApiError,
  type Lab,
  type LoggedRun,
  type ReplayRequest,
  type ReplayResponse,
  exportUrl,
  labelExperiment,
  listExperiments,
  replayExperiment,
} from "@/lib/api/client";
import openapi from "@/lib/api/openapi.json";
import { fileToBase64 } from "@/lib/quant/upload";
import { reopenLink } from "@/lib/runs/pages";

/** Runs fetched at a time. A shorter page means there are no more. */
export const PAGE_SIZE = 50;

// The server's limits, read from the API contract so the two cannot disagree.
const LABEL_LIMITS = openapi.components.schemas.RunLabels.properties as {
  name: { anyOf: { maxLength?: number }[] };
  note: { anyOf: { maxLength?: number }[] };
};
const maxLength = (field: { anyOf: { maxLength?: number }[] }) =>
  field.anyOf.find((t) => t.maxLength !== undefined)?.maxLength;
const NAME_MAX = maxLength(LABEL_LIMITS.name);
const NOTE_MAX = maxLength(LABEL_LIMITS.note);

type Editing = { runId: string; name: string; note: string; error: string | null };

const VERDICT_LABEL: Record<ReplayResponse["verdict"], string> = {
  identical: "Identical",
  within_tolerance: "Within tolerance",
  differs: "Differs",
};

type ReplayState =
  | { status: "running" }
  | { status: "done"; result: ReplayResponse }
  | { status: "failed"; message: string };

/** The verdict of one replay, in words. */
function ReplayOutcome({ state }: { state: ReplayState }) {
  if (state.status === "running") return <p className="note">Replaying…</p>;
  if (state.status === "failed")
    return (
      <p className="api-error" role="alert">
        {state.message}
      </p>
    );
  const r = state.result;
  const d = r.largest_difference;
  return (
    <div className="replay-outcome" data-verdict={r.verdict}>
      <p>
        <strong>{VERDICT_LABEL[r.verdict]}.</strong> {r.explanation}
      </p>
      {d && (
        <p className="note">
          Largest difference: <code>{d.field}</code> {String(d.original)} → {String(d.replay)}
          {d.within_tolerance ? " (within its tolerance)" : " (outside its tolerance)"}.
        </p>
      )}
      {!r.environment_matches && (
        <p className="note">
          Environment differs: {r.environment_differences.map((e) => e.key).join(", ")}.
        </p>
      )}
    </div>
  );
}

const LABS: { id: Lab | null; label: string }[] = [
  { id: null, label: "All" },
  { id: "physics", label: "Physics" },
  { id: "economy", label: "Economy" },
  { id: "quant", label: "Quant" },
];

export function ExperimentLog() {
  const [lab, setLab] = useState<Lab | null>(null);
  const [runs, setRuns] = useState<LoggedRun[] | null>(null);
  const [more, setMore] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveReplays, setSaveReplays] = useState(false);
  const [replays, setReplays] = useState<Record<string, ReplayState>>({});
  const [editing, setEditing] = useState<Editing | null>(null);

  async function saveLabels(edit: Editing) {
    try {
      const updated = await labelExperiment(edit.runId, { name: edit.name, note: edit.note });
      setRuns((prev) => prev?.map((r) => (r.run_id === updated.run_id ? updated : r)) ?? prev);
      setEditing(null);
    } catch (err) {
      setEditing({
        ...edit,
        error: err instanceof ApiError ? err.message : "Could not save the labels.",
      });
    }
  }

  async function replay(run: LoggedRun, file?: File) {
    const set = (state: ReplayState) => setReplays((prev) => ({ ...prev, [run.run_id]: state }));
    set({ status: "running" });
    try {
      const body: ReplayRequest = { save_experiment: saveReplays };
      if (file) body.dataset = { content_base64: await fileToBase64(file) };
      set({ status: "done", result: await replayExperiment(run.run_id, body) });
    } catch (err) {
      set({
        status: "failed",
        message: err instanceof ApiError ? err.message : "Could not replay this run.",
      });
    }
  }

  const fail = (err: unknown) =>
    setError(err instanceof ApiError ? err.message : "Unexpected error");

  // The first page of the chosen lab. State is set only when the reply arrives, and a reply
  // for a lab that is no longer chosen is dropped.
  useEffect(() => {
    let current = true;
    listExperiments({ lab: lab ?? undefined, limit: PAGE_SIZE })
      .then((page) => {
        if (!current) return;
        setRuns(page);
        setMore(page.length === PAGE_SIZE);
      })
      .catch((err: unknown) => current && fail(err));
    return () => {
      current = false;
    };
  }, [lab]);

  function chooseLab(next: Lab | null) {
    setLab(next);
    setRuns(null);
    setError(null);
  }

  async function loadMore() {
    setLoading(true);
    try {
      const page = await listExperiments({
        lab: lab ?? undefined,
        limit: PAGE_SIZE,
        offset: runs?.length ?? 0,
      });
      setRuns((prev) => [...(prev ?? []), ...page]);
      setMore(page.length === PAGE_SIZE);
    } catch (err) {
      fail(err);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="card">
      <div className="lab-filter" role="group" aria-label="Show runs from">
        {LABS.map((l) => (
          <button
            key={l.label}
            type="button"
            className="secondary"
            aria-pressed={lab === l.id}
            onClick={() => chooseLab(l.id)}
          >
            {l.label}
          </button>
        ))}
      </div>
      <label className="checkbox">
        <input
          type="checkbox"
          checked={saveReplays}
          onChange={(e) => setSaveReplays(e.target.checked)}
        />
        Save replays to the log (each as a new run linked to the original)
      </label>
      {error && (
        <p className="api-error" role="alert">
          {error}
        </p>
      )}
      {runs === null ? (
        <p className="note">Loading…</p>
      ) : runs.length === 0 ? (
        <p className="empty">No saved runs here yet. Run a model with saving switched on.</p>
      ) : (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th scope="col">Created (UTC)</th>
                <th scope="col">Model</th>
                <th scope="col">Result</th>
                <th scope="col">Run</th>
                <th scope="col">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <Fragment key={r.run_id}>
                  <tr>
                    <td>{r.created_at.slice(0, 19).replace("T", " ")}</td>
                    <td>
                      {r.model_id} <span className="unit">v{r.model_version}</span>
                    </td>
                    <td>
                      {r.name && <strong className="run-name">{r.name}</strong>}
                      {r.headline}
                      {r.note && <span className="check-kind run-note">{r.note}</span>}
                      {r.replay_of && (
                        <span className="check-kind">replay of {r.replay_of.slice(0, 8)}</span>
                      )}
                    </td>
                    <td>
                      <code title={r.run_id}>{r.run_id.slice(0, 8)}</code>
                    </td>
                    <td>
                      <div className="actions-inner">
                        {reopenLink(r.model_id, r.run_id) && (
                          <a href={reopenLink(r.model_id, r.run_id)!}>Open</a>
                        )}
                        {/* The server names the file <model>_<run8>.json; labels never appear. */}
                        <a href={exportUrl(r.run_id)} download>
                          Export JSON
                        </a>
                        <button
                          type="button"
                          className="secondary"
                          onClick={() =>
                            setEditing({
                              runId: r.run_id,
                              name: r.name ?? "",
                              note: r.note ?? "",
                              error: null,
                            })
                          }
                        >
                          Edit labels
                        </button>
                        {r.replay_needs_file ? (
                          <label className="button secondary">
                            Replay with file
                            <input
                              type="file"
                              accept=".csv,text/csv,text/plain"
                              className="sr-only"
                              disabled={replays[r.run_id]?.status === "running"}
                              onChange={(e) => {
                                const file = e.target.files?.[0];
                                if (file) void replay(r, file);
                              }}
                            />
                          </label>
                        ) : (
                          <button
                            type="button"
                            className="secondary"
                            disabled={replays[r.run_id]?.status === "running"}
                            onClick={() => void replay(r)}
                          >
                            Replay
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                  {editing?.runId === r.run_id && (
                    <tr className="replay-row">
                      <td colSpan={5}>
                        <form
                          className="label-form"
                          aria-label={`Labels for run ${r.run_id.slice(0, 8)}`}
                          onSubmit={(e) => {
                            e.preventDefault();
                            void saveLabels(editing);
                          }}
                        >
                          <div className="field">
                            <label htmlFor={`name-${r.run_id}`}>Name</label>
                            <input
                              id={`name-${r.run_id}`}
                              type="text"
                              maxLength={NAME_MAX}
                              value={editing.name}
                              onChange={(e) => setEditing({ ...editing, name: e.target.value })}
                            />
                          </div>
                          <div className="field">
                            <label htmlFor={`note-${r.run_id}`}>Note</label>
                            <textarea
                              id={`note-${r.run_id}`}
                              rows={2}
                              maxLength={NOTE_MAX}
                              value={editing.note}
                              onChange={(e) => setEditing({ ...editing, note: e.target.value })}
                            />
                          </div>
                          <p className="note">
                            Labels help you find runs; they never change a run&rsquo;s inputs or
                            results.
                          </p>
                          <button type="submit">Save labels</button>{" "}
                          <button
                            type="button"
                            className="secondary"
                            onClick={() => setEditing(null)}
                          >
                            Cancel
                          </button>
                          {editing.error && (
                            <p className="api-error" role="alert">
                              {editing.error}
                            </p>
                          )}
                        </form>
                      </td>
                    </tr>
                  )}
                  {replays[r.run_id] && (
                    <tr className="replay-row">
                      <td colSpan={5}>
                        <ReplayOutcome state={replays[r.run_id]!} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {more && (
        <button
          type="button"
          className="secondary"
          disabled={loading}
          onClick={() => void loadMore()}
        >
          Load more
        </button>
      )}
    </div>
  );
}
