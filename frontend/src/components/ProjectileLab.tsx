"use client";

import { type FormEvent, useState } from "react";

import {
  ApiError,
  type ProjectileResponse,
  type SolverSettings,
  simulateProjectile,
} from "@/lib/api/client";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import {
  PARAMETER_FIELDS,
  SOLVER_FIELDS,
  SOLVER_METHODS,
  toProjectileParameters,
} from "@/lib/projectile/fields";
import { NumberField } from "./NumberField";
import {
  ProjectileAssumptions,
  ProjectileCharts,
  ProjectileSummary,
  ProjectileValidation,
} from "./ProjectileResults";
import { STALE_INPUTS_NOTE, Workspace, runStatus } from "./Workspace";

type FormValues = Record<string, string>;

const ALL_FIELDS: readonly NumericFieldSpec[] = [...PARAMETER_FIELDS, ...SOLVER_FIELDS];
const INITIAL_VALUES: FormValues = Object.fromEntries(
  ALL_FIELDS.map((f) => [f.name, String(f.default)]),
);

export function ProjectileLab() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [method, setMethod] = useState<SolverSettings["method"]>("DOP853");
  const [touched, setTouched] = useState(false);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<ProjectileResponse | null>(null);
  // Everything the result depends on, as one string: the result is current only while the
  // form still matches the inputs it was computed from.
  const [resultKey, setResultKey] = useState<string | null>(null);
  const currentKey = JSON.stringify([values, method]);

  const errors = Object.fromEntries(
    ALL_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  const hasErrors = Object.values(errors).some((e) => e !== null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors) return;
    const num = (name: string) => Number(values[name]);
    const key = currentKey;
    setStatus("running");
    setApiError(null);
    try {
      setResult(
        await simulateProjectile({
          parameters: toProjectileParameters(values),
          solver: { method, rtol: num("rtol"), atol: num("atol") },
        }),
      );
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
    <form onSubmit={onSubmit} noValidate aria-label="Simulation inputs">
      <fieldset>
        <legend>Physical parameters</legend>
        {PARAMETER_FIELDS.map(field)}
      </fieldset>
      <fieldset>
        <legend>Numerical solver</legend>
        <div className="field">
          <label htmlFor="field-method">Method</label>
          <select
            id="field-method"
            value={method}
            onChange={(e) => setMethod(e.target.value as SolverSettings["method"])}
          >
            {SOLVER_METHODS.map((m) => (
              <option key={m} value={m}>
                {m}
              </option>
            ))}
          </select>
        </div>
        {SOLVER_FIELDS.map(field)}
      </fieldset>
      <button type="submit" disabled={status === "running"}>
        {status === "running" ? "Running…" : "Run simulation"}
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
      visualisation={result && <ProjectileCharts result={result} />}
      results={result && <ProjectileSummary result={result} />}
      assumptions={result && <ProjectileAssumptions result={result} />}
      validation={result && <ProjectileValidation result={result} />}
      placeholders={{
        visualisation:
          "Set the parameters and run the simulation. The trajectory and energy budget appear " +
          "here.",
        results:
          "Flight time, range, maximum height and impact speed from the analytical solution.",
        assumptions: "The model's assumptions are listed with every run.",
        validation:
          "SimForge solves the motion twice, analytically and with an adaptive Runge–Kutta " +
          "solver, and reports here how far apart the two are.",
      }}
    />
  );
}
