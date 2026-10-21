"use client";

import { type FormEvent, useState } from "react";

import { ApiError, type SolowRequest, type SolowResponse, simulateSolow } from "@/lib/api/client";
import {
  ALL_SOLOW_FIELDS,
  ECONOMY_FIELDS,
  POLICY_FIELDS,
  START_FIELDS,
  effectiveDepreciationProblem,
} from "@/lib/economy/solowFields";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import { NumberField } from "./NumberField";
import { SolowAssumptions, SolowCharts, SolowSummary, SolowValidation } from "./SolowResults";
import { STALE_INPUTS_NOTE, Workspace, runStatus } from "./Workspace";

type FormValues = Record<string, string>;

const INITIAL_VALUES: FormValues = Object.fromEntries(
  ALL_SOLOW_FIELDS.map((f) => [f.name, String(f.default)]),
);

function fieldErrors(values: FormValues): Record<string, string | null> {
  const errors = Object.fromEntries(
    ALL_SOLOW_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  // Cross-field rules mirrored from the server (which remains the authority).
  if (!errors.population_growth && !errors.technology_growth && !errors.depreciation) {
    errors.depreciation = effectiveDepreciationProblem(
      Number(values.population_growth),
      Number(values.technology_growth),
      Number(values.depreciation),
    );
  }
  if (!errors.policy_year && !errors.horizon_years) {
    if (Number(values.policy_year) >= Number(values.horizon_years)) {
      errors.policy_year = "Must be below the horizon";
    }
  }
  return errors;
}

export function SolowLab() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [touched, setTouched] = useState(false);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<SolowResponse | null>(null);
  const [resultKey, setResultKey] = useState<string | null>(null);
  const currentKey = JSON.stringify(values);

  const errors = fieldErrors(values);
  const hasErrors = Object.values(errors).some((e) => e !== null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors) return;
    const num = (name: string) => Number(values[name]);
    // Written out field by field so tsc checks every name against the generated contract.
    const body: SolowRequest = {
      parameters: {
        capital_share: num("capital_share"),
        savings_rate: num("savings_rate"),
        depreciation: num("depreciation"),
        population_growth: num("population_growth"),
        technology_growth: num("technology_growth"),
        initial_capital_ratio: num("initial_capital_ratio"),
      },
      policy: { new_savings_rate: num("new_savings_rate"), policy_year: num("policy_year") },
      horizon_years: num("horizon_years"),
    };
    const key = currentKey;
    setStatus("running");
    setApiError(null);
    try {
      setResult(await simulateSolow(body));
      setResultKey(key);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setStatus("idle");
    }
  }

  const field = (f: NumericFieldSpec) => (
    <NumberField
      key={f.name}
      field={f}
      value={values[f.name] ?? ""}
      error={touched ? (errors[f.name] ?? null) : null}
      onChange={(v) => setValues((prev) => ({ ...prev, [f.name]: v }))}
    />
  );

  const form = (
    <form onSubmit={onSubmit} noValidate aria-label="Solow model inputs">
      <fieldset>
        <legend>Economy</legend>
        {ECONOMY_FIELDS.map(field)}
      </fieldset>
      <fieldset>
        <legend>Starting point</legend>
        {START_FIELDS.map(field)}
      </fieldset>
      <fieldset>
        <legend>Savings policy</legend>
        {POLICY_FIELDS.map(field)}
      </fieldset>
      <p className="note">Rates are fractions per year: 0.02 means 2% per year.</p>
      <button type="submit" disabled={status === "running"}>
        {status === "running" ? "Running…" : "Run model"}
      </button>
      {apiError && (
        <p className="api-error" role="alert">
          {apiError}
        </p>
      )}
    </form>
  );

  return (
    <Workspace
      parameters={form}
      status={runStatus(status, result)}
      staleNote={result && resultKey !== currentKey ? STALE_INPUTS_NOTE : null}
      visualisation={result && <SolowCharts result={result} />}
      results={result && <SolowSummary result={result} />}
      assumptions={result && <SolowAssumptions result={result} />}
      validation={result && <SolowValidation result={result} />}
      placeholders={{
        visualisation:
          "Run the model to see capital, consumption and output per worker over time, for " +
          "the baseline and for the savings-policy scenario.",
        results: "Steady states and convergence appear here.",
        assumptions: "The model's assumptions are listed with every run.",
        validation: "Each run reports its own numerical checks here.",
      }}
    />
  );
}
