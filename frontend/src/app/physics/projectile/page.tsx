import type { Metadata } from "next";

import { ProjectileLab } from "@/components/ProjectileLab";

export const metadata: Metadata = { title: "Projectile motion" };

export default function ProjectilePage() {
  return (
    <>
      <header className="page-header">
        <p className="eyebrow">Physics Lab</p>
        <h1>Projectile motion with linear drag</h1>
        <p>
          A point mass under uniform gravity with drag force <i>F</i> = −<i>b</i>
          <b>v</b>. This case has an exact solution, so the numerical solver can be checked against
          it. Set <i>b</i> = 0 for motion in a vacuum.
        </p>
      </header>
      <ProjectileLab />
    </>
  );
}
