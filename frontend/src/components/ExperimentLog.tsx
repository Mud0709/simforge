"use client";

import { useEffect, useState } from "react";

import { ApiError, type Lab, type LoggedRun, listExperiments } from "@/lib/api/client";
import { reopenLink } from "@/lib/runs/pages";

/** Runs fetched at a time. A shorter page means there are no more. */
export const PAGE_SIZE = 50;

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
                <tr key={r.run_id}>
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
                  <td>
                    {reopenLink(r.model_id, r.run_id) && (
                      <a href={reopenLink(r.model_id, r.run_id)!}>Open</a>
                    )}
                  </td>
                </tr>
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
