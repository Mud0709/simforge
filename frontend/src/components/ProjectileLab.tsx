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
import {
  ProjectileAssumptions,
  ProjectileCharts,
  ProjectileSummary,
  ProjectileValidation,
} from "./ProjectileResults";
import { Workspace } from "./Workspace";

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

  const empty = (text: string) => <p className="empty">{text}</p>;

  return (
    <Workspace
      parameters={form}
      visualisation={
        result ? (
          <ProjectileCharts result={result} />
        ) : (
          empty(
            "Set the parameters and run the simulation. The trajectory and energy budget appear " +
              "here.",
          )
        )
      }
      results={
        result ? (
          <ProjectileSummary result={result} />
        ) : (
          empty("Flight time, range, maximum height and impact speed from the exact solution.")
        )
      }
      assumptions={
        result ? (
          <ProjectileAssumptions result={result} />
        ) : (
          empty("The model's assumptions are listed with every run.")
        )
      }
      validation={
        result ? (
          <ProjectileValidation result={result} />
        ) : (
          empty(
            "SimForge solves the motion twice, exactly and with an adaptive Runge–Kutta solver, " +
              "and reports here how far apart the two are.",
          )
        )
      }
    />
  );
}
