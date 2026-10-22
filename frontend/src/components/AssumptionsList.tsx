import type { Assumption } from "@/lib/api/client";

/** A model's stated assumptions, as returned with every run (shared by all three labs). */
export function AssumptionsList({ assumptions }: { assumptions: Assumption[] }) {
  return (
    <ul className="assumptions">
      {assumptions.map((a) => (
        <li key={a.id}>{a.statement}</li>
      ))}
    </ul>
  );
}
