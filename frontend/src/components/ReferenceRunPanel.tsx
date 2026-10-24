"use client";

import type { ModelResponse } from "@/lib/api/client";
import type { ModelId } from "@/lib/api/models";
import type { Provenance, ReferenceRun } from "./useReferenceRun";

/** How the reference's curves were obtained, in the words shown next to it. */
export function provenanceLabel(p: Provenance): string {
  switch (p.kind) {
    case "recomputed":
      if (p.digestMatch === true) return "recomputed, bit-identical";
      if (p.digestMatch === false)
        return "recomputed, not bit-identical (cause not checked; usually another CPU or library version)";
      return "recomputed; cannot be checked (older record without a digest)";
    case "session":
      return "computed in this session; saved, so a reload recomputes it from the experiment log";
    case "memory":
      return p.why === "upload"
        ? "a profile of an uploaded file, which is never stored: held in this tab, lost on reload"
        : "not saved: held in this tab only, lost on reload";
  }
}

/** A warning when the reference and `current` are the same model at different versions. */
export function versionWarning(
  reference: ModelResponse | null,
  current: ModelResponse | null,
): string | null {
  if (!reference || !current || reference.model.id !== current.model.id) return null;
  const [was, now] = [reference.model.version, current.model.version];
  if (was === now) return null;
  return (
    `The reference run used ${reference.model.id} v${was}; this run uses v${now}. Different ` +
    "model versions run different code, so the curves may differ for that reason as well as " +
    "because of the inputs."
  );
}

const withArticle = (word: string) => `${/^[aeiou]/i.test(word) ? "an" : "a"} ${word}`;

/**
 * The reference run of a lab page: what it is and where its curves came from, and the
 * controls to pin the run on screen or unpin the reference. `modelIds` are the models this
 * page draws; a reference from any other model is kept but never overlaid.
 */
export function ReferenceRunPanel({
  run,
  current,
  modelIds,
}: {
  run: ReferenceRun;
  current: ModelResponse | null;
  modelIds: readonly ModelId[];
}) {
  const ref = run.reference;
  const short = ref?.runId.slice(0, 8);
  const ready = ref?.status === "ready" ? ref : null;
  const pinnable = current !== null && ready?.runId !== current.metadata.run_id;
  const otherModel = ready && !modelIds.some((id) => id === ready.response.model.id);
  const warning = versionWarning(run.response, current);

  return (
    <>
      {!ref && (
        <p className="note">
          Pin this run as the reference run, then change the inputs and run again: the
          reference&rsquo;s curves are drawn faded under the new run&rsquo;s.
        </p>
      )}
      {ref?.status === "loading" && (
        <p className="note">Recomputing reference run {short} from the experiment log…</p>
      )}
      {ref?.status === "refused" && (
        <p className="api-error" role="alert">
          {ref.message} The page works as usual, without a reference run.
        </p>
      )}
      {ready && (
        <dl className="meta">
          <dt>Reference run</dt>
          <dd>
            <code title={ready.runId}>{short}</code> · {ready.response.model.name} v
            {ready.response.model.version}
          </dd>
          <dt>Its curves</dt>
          <dd data-testid="reference-provenance">{provenanceLabel(ready.provenance)}</dd>
        </dl>
      )}
      {otherModel && (
        <p className="api-error">
          Reference run {short} is {withArticle(ready.response.model.id)} run. A reference run is
          drawn only over runs of the same model, so it is not overlaid here.
        </p>
      )}
      {ready?.response.model.id === "quant.dataset_profile" && !otherModel && (
        <p className="note">A dataset profile has no curves to overlay: the reference is kept.</p>
      )}
      {warning && <p className="api-error">{warning}</p>}
      {(pinnable || ref) && (
        <div className="download-buttons" role="group" aria-label="Reference run">
          {pinnable && current && (
            <button type="button" className="secondary" onClick={() => run.pin(current)}>
              Pin as reference run
            </button>
          )}
          {ref && (
            <button type="button" className="secondary" onClick={run.unpin}>
              Unpin reference run
            </button>
          )}
        </div>
      )}
    </>
  );
}
