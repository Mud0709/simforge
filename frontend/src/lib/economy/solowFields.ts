import openapi from "@/lib/api/openapi.json";
import { type NumericFieldSpec, spec } from "@/lib/fields";

// Rates are fractions per year, exactly as the API takes them (0.02 = 2% per year). The form
// never converts from percent, so what you type is what is hashed and stored.
export const ECONOMY_FIELDS = [
  spec("SolowParameters", "capital_share", "Capital share α", ""),
  spec("SolowParameters", "depreciation", "Depreciation δ", "per year"),
  spec("SolowParameters", "population_growth", "Population growth n", "per year"),
  spec("SolowParameters", "technology_growth", "Technology growth g", "per year"),
] as const satisfies readonly NumericFieldSpec[];

export const START_FIELDS = [
  spec("SolowParameters", "savings_rate", "Savings rate s₀", "of output"),
  spec("SolowParameters", "initial_capital_ratio", "Initial capital", "× k*(s₀)"),
] as const satisfies readonly NumericFieldSpec[];

export const POLICY_FIELDS = [
  spec("SavingsPolicy", "new_savings_rate", "New savings rate s₁", "of output"),
  spec("SavingsPolicy", "policy_year", "Policy year", "year"),
  spec("SolowRequest", "horizon_years", "Horizon", "years"),
] as const satisfies readonly NumericFieldSpec[];

const solowParameters = openapi.components.schemas.SolowParameters as {
  "x-min-effective-depreciation"?: number;
};
const minLambda = solowParameters["x-min-effective-depreciation"];
if (typeof minLambda !== "number") {
  throw new Error("OpenAPI schema SolowParameters has no x-min-effective-depreciation");
}
/** The server's lower bound on λ = n + g + ng + δ, read from the API contract. */
export const MIN_EFFECTIVE_DEPRECIATION: number = minLambda;

/**
 * The server's cross-field rule (which remains the authority): λ = n + g + ng + δ must be at
 * least the bound, with the same relative slack for float rounding. Returns an error or null.
 */
export function effectiveDepreciationProblem(n: number, g: number, delta: number): string | null {
  const lambda = n + g + n * g + delta;
  if (lambda >= MIN_EFFECTIVE_DEPRECIATION * (1 - 1e-12)) return null;
  return (
    `n + g + ng + δ = ${Number(lambda.toPrecision(6))} is below ${MIN_EFFECTIVE_DEPRECIATION}: ` +
    "capital would not settle at a steady state within any useful horizon. Raise δ, n or g."
  );
}

export const ALL_SOLOW_FIELDS: readonly NumericFieldSpec[] = [
  ...ECONOMY_FIELDS,
  ...START_FIELDS,
  ...POLICY_FIELDS,
];
