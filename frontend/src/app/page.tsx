import Link from "next/link";

const MODULES = [
  {
    name: "Physics Lab",
    href: "/physics/projectile",
    status: "Projectile model and integrator study available",
    description:
      "Simulate motion, collisions, energy transfer and orbital mechanics. Adjust parameters, " +
      "compare numerical results with theoretical predictions, and graph the outcomes.",
  },
  {
    name: "Economy Lab",
    href: null,
    status: "Planned",
    description:
      "Experiment with interest rates, taxes, government spending and supply shocks. Observe " +
      "their effects on inflation, output and unemployment over time.",
  },
  {
    name: "Quant Research Lab",
    href: null,
    status: "Planned",
    description:
      "Import datasets, fit statistical models, test hypotheses, examine uncertainty and run " +
      "reproducible experiments on historical data.",
  },
] as const;

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
