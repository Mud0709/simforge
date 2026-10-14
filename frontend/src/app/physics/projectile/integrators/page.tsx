import type { Metadata } from "next";
import Link from "next/link";

import { IntegratorLab } from "@/components/IntegratorLab";

export const metadata: Metadata = { title: "Integrator convergence" };

export default function IntegratorsPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Physics Lab · Numerical methods</p>
        <h1>How fast do integrators converge?</h1>
        <p>
          Forward Euler, classical RK4 and velocity Verlet, written from scratch, solve the{" "}
          <Link href="/physics/projectile">projectile-with-drag</Link> problem at fixed time steps
          <i> h</i>. Because this problem has an exact solution, the error of each method can be
          measured directly. Theory predicts error ∝ <i>h</i>
          <sup>p</sup> with p = 1, 4 and 2, as long as the step is small and the method is stable.
        </p>
      </header>
      <IntegratorLab />
    </>
  );
}
