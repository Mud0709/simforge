"use client";

import { useEffect, useState } from "react";

import { ApiError, type LoggedRun, getExperiment } from "@/lib/api/client";

/**
 * If the page was opened with `?run=<id>`, fetch that run and hand it to `apply` (which fills
 * the form). Nothing is run: the user presses Run. Returns a note to show, or an error if the
 * run is missing or belongs to another model.
 */
export function useReopenedRun(
  modelIds: readonly string[],
  apply: (run: LoggedRun) => string | void,
): { note: string | null; error: string | null } {
  const [note, setNote] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const runId = new URLSearchParams(window.location.search).get("run");
    if (!runId) return;
    let current = true;
    getExperiment(runId)
      .then((run) => {
        if (!current) return;
        if (!modelIds.includes(run.model_id)) {
          setError(
            `Run ${runId.slice(0, 8)} is a ${run.model_id} run, which this page does not show. ` +
              "Open it from the experiment log.",
          );
          return;
        }
        const extra = apply(run);
        setNote(
          `Loaded the inputs of run ${runId.slice(0, 8)} (saved ` +
            `${run.created_at.slice(0, 16).replace("T", " ")} UTC). Press Run to compute it ` +
            `again.${extra ? ` ${extra}` : ""}`,
        );
      })
      .catch((err: unknown) => {
        if (current) setError(err instanceof ApiError ? err.message : "Unexpected error");
      });
    return () => {
      current = false;
    };
    // Reads the URL once, when the page opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { note, error };
}
