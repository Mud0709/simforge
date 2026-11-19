import type { Metadata } from "next";
import Link from "next/link";

import { OscillatorIntegratorLab } from "@/components/OscillatorIntegratorLab";

export const metadata: Metadata = { title: "Oscillator integrators" };

export default function OscillatorIntegratorsPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Physics Lab · Numerical methods</p>
        <h1>Do symplectic integrators keep the energy?</h1>
        <p>
          Forward Euler, RK4, symplectic Euler and velocity Verlet, written from scratch, integrate
          the undamped <Link href="/physics/oscillator">oscillator</Link>. Over one period the error
          of each shrinks as <i>h</i>
          <sup>p</sup>; over many periods the symplectic methods keep the energy within a bound
          while Euler gains and RK4 slowly loses it.
        </p>
      </header>
      <OscillatorIntegratorLab />
    </>
  );
}
