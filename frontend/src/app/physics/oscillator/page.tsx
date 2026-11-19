import type { Metadata } from "next";
import Link from "next/link";

import { OscillatorLab } from "@/components/OscillatorLab";

export const metadata: Metadata = { title: "Harmonic oscillator" };

export default function OscillatorPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Physics Lab</p>
        <h1>Harmonic oscillator: simple, damped and driven</h1>
        <p>
          A mass on a spring, <i>m</i>x″ + <i>b</i>x′ + <i>k</i>x = <i>F</i>₀ cos(<i>ωt</i>). Choose
          a preset or set the mass, spring, damping and drive yourself. The solver&apos;s answer is
          compared with the exact solution, the energy balance is checked, and a driven run shows
          its resonance curve.
        </p>
        <p>
          <Link href="/physics/oscillator/integrators">Compare integrators on the oscillator</Link>
        </p>
      </header>
      <OscillatorLab />
    </>
  );
}
