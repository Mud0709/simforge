import type { ReactNode } from "react";

/**
 * The scientific workspace every lab model uses: inputs on the left; on the right, what the
 * model shows (visualisation), what it computed (results), what it assumes, and how this
 * run was checked (validation). Functional layout only; visual polish comes later.
 */
export function Workspace({
  parameters,
  visualisation,
  results,
  assumptions,
  validation,
}: {
  parameters: ReactNode;
  visualisation: ReactNode;
  results: ReactNode;
  assumptions: ReactNode;
  validation: ReactNode;
}) {
  return (
    <div className="workspace">
      <Section id="parameters" title="Parameters" className="ws-parameters">
        {parameters}
      </Section>
      <div className="ws-main" aria-live="polite">
        <Section id="visualisation" title="Visualisation">
          {visualisation}
        </Section>
        <Section id="results" title="Results">
          {results}
        </Section>
        <div className="ws-pair">
          <Section id="assumptions" title="Assumptions">
            {assumptions}
          </Section>
          <Section id="validation" title="Validation">
            {validation}
          </Section>
        </div>
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
