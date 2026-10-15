"use client";

import { type FormEvent, useState } from "react";

import { ApiError, type SolowRequest, type SolowResponse, simulateSolow } from "@/lib/api/client";
import {
  ALL_SOLOW_FIELDS,
  ECONOMY_FIELDS,
  POLICY_FIELDS,
  START_FIELDS,
} from "@/lib/economy/solowFields";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import { NumberField } from "./NumberField";
import { SolowAssumptions, SolowCharts, SolowSummary, SolowValidation } from "./SolowResults";
import { Workspace } from "./Workspace";

type FormValues = Record<string, string>;

const INITIAL_VALUES: FormValues = Object.fromEntries(
  ALL_SOLOW_FIELDS.map((f) => [f.name, String(f.default)]),
);

function fieldErrors(values: FormValues): Record<string, string | null> {
  const errors = Object.fromEntries(
    ALL_SOLOW_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  // Cross-field rule mirrored from the server (which remains the authority).
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

  const errors = fieldErrors(values);
  const hasErrors = Object.values(errors).some((e) => e !== null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors) return;
    const num = (name: string) => Number(values[name]);
    const body: SolowRequest = {
      parameters: Object.fromEntries(
        [...ECONOMY_FIELDS, ...START_FIELDS].map((f) => [f.name, num(f.name)]),
      ) as unknown as SolowRequest["parameters"],
      policy: { new_savings_rate: num("new_savings_rate"), policy_year: num("policy_year") },
      horizon_years: num("horizon_years"),
    };
    setStatus("running");
    setApiError(null);
    try {
      setResult(await simulateSolow(body));
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

  const empty = (text: string) => <p className="empty">{text}</p>;

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
      visualisation={
        result ? (
          <SolowCharts result={result} />
        ) : (
          empty(
            "Run the model to see capital, consumption and output per worker over time, for " +
              "the baseline and for the savings-policy scenario.",
          )
        )
      }
      results={
        result ? (
          <SolowSummary result={result} />
        ) : (
          empty("Steady states and convergence appear here.")
        )
      }
      assumptions={
        result ? (
          <SolowAssumptions result={result} />
        ) : (
          empty("The model's assumptions are listed with every run.")
        )
      }
      validation={
        result ? (
          <SolowValidation result={result} />
        ) : (
          empty("Each run reports its own numerical checks here.")
        )
      }
    />
  );
}
