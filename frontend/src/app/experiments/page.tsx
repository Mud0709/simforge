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
          Every saved run from all three labs, with the inputs, software versions and a fingerprint
          of its outputs. <strong>Open</strong> loads a run&rsquo;s inputs back into its page;{" "}
          <strong>Replay</strong> reruns it and says whether the same answer came back. Names and
          notes are labels: they never change a run&rsquo;s results.
        </p>
      </header>
      <ExperimentLog />
    </>
  );
}
