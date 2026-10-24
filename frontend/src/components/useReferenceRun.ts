"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { ApiError, type ModelResponse, recomputeOutputs } from "@/lib/api/client";
import { isModelResponse } from "@/lib/api/models";

/** Where the reference's curves came from, shown next to it. */
export type Provenance =
  /** Computed again from the experiment log (`?ref=` on load), with the digest's verdict. */
  | { kind: "recomputed"; digestMatch: boolean | null }
  /** The saved run on screen, pinned in this session; `?ref=` brings it back after a reload. */
  | { kind: "session" }
  /** Held in this tab only: an unsaved run, or a profile of a file the server never stores. */
  | { kind: "memory"; why: "unsaved" | "upload" };

export type Reference =
  | { status: "loading"; runId: string }
  | { status: "refused"; runId: string; message: string }
  | { status: "ready"; runId: string; response: ModelResponse; provenance: Provenance };

export interface ReferenceRun {
  reference: Reference | null;
  /** The reference's response once it is loaded, else null: what the charts overlay. */
  response: ModelResponse | null;
  pin: (response: ModelResponse) => void;
  unpin: () => void;
}

/** Sets or removes `?ref=` without reloading, keeping every other part of the address. */
function setRefParam(runId: string | null) {
  const url = new URL(window.location.href);
  if (runId === null) url.searchParams.delete("ref");
  else url.searchParams.set("ref", runId);
  window.history.replaceState(window.history.state, "", url);
}

/** Why a run cannot be pinned by its id (and so is kept in memory), or null if it can. */
function heldInMemory(response: ModelResponse): Provenance | null {
  // A saved upload profile has a record, but recomputing it needs the file again.
  if (isModelResponse(response, "quant.dataset_profile") && response.dataset.source === "upload")
    return { kind: "memory", why: "upload" };
  if (!response.metadata.experiment_saved) return { kind: "memory", why: "unsaved" };
  return null;
}

/**
 * The page's reference run (roadmap 1.6, D6). If the page was opened with `?ref=<id>`, that
 * saved run is recomputed through `POST /experiments/{id}/outputs` (the log stores no
 * curves). Pinning a saved run puts its id in the URL; an unsaved run, or an uploaded file's
 * profile, is held in memory only and is lost on reload. A refusal (409, 422, 404) is kept
 * as a message: the page works as usual without a reference.
 */
export function useReferenceRun(): ReferenceRun {
  const [reference, setReference] = useState<Reference | null>(null);
  // Bumped by every pin and unpin, so a slow recomputation cannot undo a newer choice.
  const generation = useRef(0);

  useEffect(() => {
    const runId = new URLSearchParams(window.location.search).get("ref");
    if (!runId) return;
    const mine = ++generation.current;
    const short = runId.slice(0, 8);
    // The URL exists only in the browser, so it is read after mount (reading it while
    // rendering would differ from the server's HTML), and "loading" must show at once: a
    // recomputation can take seconds. No promise callback comes earlier to set it from.
    // eslint-disable-next-line react-hooks/set-state-in-effect -- browser-only state on mount
    setReference({ status: "loading", runId });
    recomputeOutputs(runId)
      .then((out) => {
        if (generation.current !== mine) return;
        setReference({
          status: "ready",
          runId: out.original_run_id,
          response: out.response,
          provenance: { kind: "recomputed", digestMatch: out.digest_match },
        });
      })
      .catch((err: unknown) => {
        if (generation.current !== mine) return;
        const why = err instanceof ApiError ? err.message : "Unexpected error";
        setReference({
          status: "refused",
          runId,
          message: `Could not load reference run ${short}: ${why}`,
        });
      });
    return () => {
      generation.current += 1;
    };
  }, []);

  const pin = useCallback((response: ModelResponse) => {
    generation.current += 1;
    const memory = heldInMemory(response);
    setRefParam(memory ? null : response.metadata.run_id);
    setReference({
      status: "ready",
      runId: response.metadata.run_id,
      response,
      provenance: memory ?? { kind: "session" },
    });
  }, []);

  const unpin = useCallback(() => {
    generation.current += 1;
    setRefParam(null);
    setReference(null);
  }, []);

  return {
    reference,
    response: reference?.status === "ready" ? reference.response : null,
    pin,
    unpin,
  };
}
