"use client";

import { type FormEvent, useState } from "react";

import {
  ApiError,
  type ProjectileParameters,
  type ProjectileResponse,
  type SolverSettings,
  simulateProjectile,
} from "@/lib/api/client";
import {
  type NumericFieldSpec,
  PARAMETER_FIELDS,
  SOLVER_FIELDS,
  SOLVER_METHODS,
  validateField,
} from "@/lib/projectile/fields";
import { NumberField } from "./NumberField";
import { ProjectileResults } from "./ProjectileResults";

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

  const errors = Object.fromEntries(
    ALL_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  const hasErrors = Object.values(errors).some((e) => e !== null);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors) return;
    const num = (name: string) => Number(values[name]);
    setStatus("running");
    setApiError(null);
    try {
      const parameters = Object.fromEntries(
        PARAMETER_FIELDS.map((f) => [f.name, num(f.name)]),
      ) as unknown as ProjectileParameters;
      setResult(
        await simulateProjectile({
          parameters,
          solver: { method, rtol: num("rtol"), atol: num("atol") },
        }),
      );
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

  return (
    <div className="lab">
      <form className="card controls" onSubmit={onSubmit} noValidate aria-label="Simulation inputs">
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

      <div aria-live="polite">
        {result ? (
          <ProjectileResults result={result} />
        ) : (
          <div className="card empty">
            <p>
              Set the parameters and run the simulation. SimForge solves the motion twice: once
              exactly, and once with an adaptive Runge–Kutta solver, and reports how far apart the
              two are.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
