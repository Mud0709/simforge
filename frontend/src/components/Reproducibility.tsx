import type { ModelResponse } from "@/lib/api/client";
import { formatSig } from "@/lib/format";

/** The run record shown under Validation: what is needed to identify and reproduce a run. */
export function Reproducibility({ metadata }: { metadata: ModelResponse["metadata"] }) {
  return (
    <>
      <h3>Reproducibility</h3>
      <dl className="meta">
        <dt>Run ID</dt>
        <dd>
          <code>{metadata.run_id}</code>
        </dd>
        <dt>Input hash</dt>
        <dd>
          <code title={metadata.input_hash}>{metadata.input_hash.slice(0, 16)}…</code>
        </dd>
        <dt>Environment</dt>
        <dd>
          SimForge {metadata.simforge_version} · Python {metadata.python_version} · NumPy{" "}
          {metadata.numpy_version} · SciPy {metadata.scipy_version}
        </dd>
        <dt>Compute time</dt>
        <dd>{formatSig(metadata.elapsed_ms, 3)} ms</dd>
        <dt>Saved to experiment log</dt>
        <dd>{metadata.experiment_saved ? "Yes" : "No"}</dd>
      </dl>
    </>
  );
}
