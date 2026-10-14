import type { Metadata } from "next";

import { ExperimentLog } from "@/components/ExperimentLog";

export const metadata: Metadata = { title: "Experiments" };

export default function ExperimentsPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Reproducibility</p>
        <h1>Experiment log</h1>
        <p>
          Each saved run records its validated inputs, solver settings, software versions and
          headline metrics. Time series are not stored: every model is deterministic, so a run can
          be regenerated from its inputs.
        </p>
      </header>
      <ExperimentLog />
    </>
  );
}
