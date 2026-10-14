import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";

import "./globals.css";

export const metadata: Metadata = {
  title: { default: "SimForge", template: "%s · SimForge" },
  description: "Interactive simulations and quantitative research with explicit assumptions.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="site-header">
          <Link href="/" className="brand">
            SimForge
          </Link>
          <nav aria-label="Main">
            <Link href="/physics/projectile">Physics Lab</Link>
            <Link href="/physics/projectile/integrators">Integrators</Link>
            <Link href="/experiments">Experiments</Link>
          </nav>
        </header>
        <main>{children}</main>
      </body>
    </html>
  );
}
