import type { Metadata } from "next";

import { SolowLab } from "@/components/SolowLab";

export const metadata: Metadata = { title: "Solow growth model" };

export default function SolowPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Economy Lab</p>
        <h1>Solow growth model</h1>
        <p>
          How much a country saves determines how much capital it builds up, and so how much it can
          produce. Change the savings rate in a chosen year and watch the economy move to a new
          steady state. Every run compares a baseline with the policy scenario, in discrete annual
          time.
        </p>
      </header>
      <SolowLab />
    </>
  );
}
