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

export const ALL_SOLOW_FIELDS: readonly NumericFieldSpec[] = [
  ...ECONOMY_FIELDS,
  ...START_FIELDS,
  ...POLICY_FIELDS,
];
