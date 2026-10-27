import Link from "next/link";

type LabCard = { name: string; href: string | null; status: string; description: string };

const MODULES: readonly LabCard[] = [
  {
    name: "Physics Lab",
    href: "/physics/projectile",
    status: "Projectile models (linear and quadratic drag) and integrator study available",
    description:
      "Simulate motion, collisions, energy transfer and orbital mechanics. Adjust parameters, " +
      "compare numerical results with theoretical predictions, and graph the outcomes.",
  },
  {
    name: "Economy Lab",
    href: "/economy/solow",
    status: "Solow growth model available",
    description:
      "Experiment with interest rates, taxes, government spending and supply shocks. Observe " +
      "their effects on inflation, output and unemployment over time.",
  },
  {
    name: "Quant Research Lab",
    href: "/quant/datasets",
    status: "CSV import and dataset profile available",
    description:
      "Import datasets, fit statistical models, test hypotheses, examine uncertainty and run " +
      "reproducible experiments on historical data.",
  },
];

export default function Home() {
  return (
    <>
      <section className="hero">
        <h1>Simulation you can check.</h1>
        <p>
          Every SimForge model states its assumptions and units, validates its inputs, and is tested
          against analytical results wherever they exist.
        </p>
      </section>
      <ul className="modules">
        {MODULES.map((m) => (
          <li key={m.name} className="card module">
            <h2>{m.name}</h2>
            <p>{m.description}</p>
            {m.href ? (
              <Link className="button" href={m.href}>
                Open {m.name}
              </Link>
            ) : (
              <span className="badge">{m.status}</span>
            )}
          </li>
        ))}
      </ul>
    </>
  );
}
