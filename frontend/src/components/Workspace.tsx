import type { ReactNode } from "react";

type OutputRegion = "visualisation" | "results" | "assumptions" | "validation";

/** Regions whose content depends on the inputs, and so can go out of date. */
const INPUT_DEPENDENT: ReadonlySet<OutputRegion> = new Set([
  "visualisation",
  "results",
  "validation",
]);

/** The note every lab shows when its inputs no longer match the results on screen. */
export const STALE_INPUTS_NOTE =
  "The inputs have changed since these results were computed. Run again to update them; " +
  "the results below are for the previous inputs.";

/** The status line for a lab's run button: running, or the run that is shown. */
export function runStatus(
  status: "idle" | "running",
  result: { metadata: { run_id: string } } | null,
): string {
  if (status === "running") return "Running…";
  return result ? `Run complete. Showing run ${result.metadata.run_id}.` : "";
}

/**
 * The scientific workspace every lab model uses: inputs on the left; on the right, what the
 * model shows (visualisation), what it computed (results), what it assumes, and how this
 * run was checked (validation). A region with no content (before the first run) shows its
 * placeholder. Functional layout only; visual polish comes later.
 */
export function Workspace({
  parameters,
  placeholders,
  status = "",
  staleNote = null,
  ...regions
}: {
  parameters: ReactNode;
  /** Each output region's content, or null/false before there is a result. */
  visualisation: ReactNode;
  results: ReactNode;
  assumptions: ReactNode;
  validation: ReactNode;
  /** What each output region says before there is anything to show. */
  placeholders: Record<OutputRegion, string>;
  /** A short line read out by screen readers when it changes (the regions are not). */
  status?: string;
  /** When set, the shown results no longer match the inputs; marked in each region. */
  staleNote?: string | null;
}) {
  const region = (id: OutputRegion, title: string) => {
    const content = regions[id];
    const hasContent = content !== null && content !== undefined && content !== false;
    return (
      <Section id={id} title={title}>
        {hasContent && staleNote && INPUT_DEPENDENT.has(id) && (
          <p className="api-error stale">{staleNote}</p>
        )}
        {hasContent ? content : <p className="empty">{placeholders[id]}</p>}
      </Section>
    );
  };
  return (
    <div className="workspace">
      <Section id="parameters" title="Parameters" className="ws-parameters">
        {parameters}
      </Section>
      <div className="ws-main">
        <p className="sr-only" role="status" aria-live="polite">
          {status}
        </p>
        {region("visualisation", "Visualisation")}
        {region("results", "Results")}
        {/* Full width: validation tables (exact vs numerical, per-run checks) need the room. */}
        {region("assumptions", "Assumptions")}
        {region("validation", "Validation")}
      </div>
    </div>
  );
}

function Section({
  id,
  title,
  className,
  children,
}: {
  id: string;
  title: string;
  className?: string;
  children: ReactNode;
}) {
  const headingId = `ws-${id}-heading`;
  return (
    <section className={`card ws-section ${className ?? ""}`} aria-labelledby={headingId}>
      <h2 id={headingId}>{title}</h2>
      {children}
    </section>
  );
}
