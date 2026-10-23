"use client";

import { Fragment, useEffect, useState } from "react";

import {
  ApiError,
  type Lab,
  type LoggedRun,
  type ReplayRequest,
  type ReplayResponse,
  listExperiments,
  replayExperiment,
} from "@/lib/api/client";
import { fileToBase64 } from "@/lib/quant/upload";
import { reopenLink } from "@/lib/runs/pages";

/** Runs fetched at a time. A shorter page means there are no more. */
export const PAGE_SIZE = 50;

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
                      {r.headline}
                      {r.replay_of && (
                        <span className="check-kind">replay of {r.replay_of.slice(0, 8)}</span>
                      )}
                    </td>
                    <td>
                      <code title={r.run_id}>{r.run_id.slice(0, 8)}</code>
                    </td>
                    <td className="actions">
                      {reopenLink(r.model_id, r.run_id) && (
                        <a href={reopenLink(r.model_id, r.run_id)!}>Open</a>
                      )}
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
                    </td>
                  </tr>
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
