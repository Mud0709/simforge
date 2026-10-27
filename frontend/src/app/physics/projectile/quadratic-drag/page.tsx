import type { Metadata } from "next";
import Link from "next/link";

import { QuadraticDragLab } from "@/components/QuadraticDragLab";

export const metadata: Metadata = { title: "Projectile motion with quadratic drag" };

export default function QuadraticDragPage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Physics Lab</p>
        <h1>Projectile motion with quadratic drag</h1>
        <p>
          A point mass under uniform gravity with drag force <i>F</i> = −<i>c</i>|<b>v</b>|<b>v</b>,
          the drag a thrown ball really feels. Unlike linear drag, this case has no exact solution
          for a 2-D flight, so the solver is checked in other ways: the exact vertical flight, the
          drag-free limit, the terminal speed, the energy balance and a conserved quantity of the
          motion. Set <i>c</i> = 0 for motion in a vacuum.
        </p>
        <p>
          <Link href="/physics/projectile">
            ← Projectile motion with linear drag (exact solution)
          </Link>
        </p>
      </header>
      <QuadraticDragLab />
    </>
  );
}
