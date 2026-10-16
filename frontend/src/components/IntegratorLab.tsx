"use client";

import { type FormEvent, useState } from "react";

import {
  ApiError,
  type IntegratorMethod,
  type IntegratorStudyResponse,
  type ProjectileParameters,
  runIntegratorStudy,
} from "@/lib/api/client";
import { DEFAULT_DT_TEXT, parseSteps } from "@/lib/integrators/steps";
import { PARAMETER_FIELDS, validateField } from "@/lib/projectile/fields";
import {
  IntegratorAssumptions,
  IntegratorCharts,
  IntegratorOrders,
  IntegratorValidation,
} from "./IntegratorResults";
import { NumberField } from "./NumberField";
import { Workspace } from "./Workspace";

export const METHOD_LABELS: Record<IntegratorMethod, string> = {
  euler: "Forward Euler (order 1)",
  rk4: "Classical RK4 (order 4)",
  verlet: "Velocity Verlet, implicit drag (order 2)",
};
const METHODS = Object.keys(METHOD_LABELS) as IntegratorMethod[];

// The study defaults to stronger drag (b = 1 kg/s) than the simulator, matching the
// backend's default: with weak drag the exponential part of the solution is too small for
// RK4's error to rise above round-off at most step sizes.
const INITIAL: Record<string, string> = {
  ...Object.fromEntries(PARAMETER_FIELDS.map((f) => [f.name, String(f.default)])),
  drag_coefficient: "1",
};

export function IntegratorLab() {
  const [values, setValues] = useState(INITIAL);
  const [stepsText, setStepsText] = useState(DEFAULT_DT_TEXT);
  const [methods, setMethods] = useState<IntegratorMethod[]>(METHODS);
  const [touched, setTouched] = useState(false);
  const [running, setRunning] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<IntegratorStudyResponse | null>(null);

  const fieldErrors = Object.fromEntries(
    PARAMETER_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  if (fieldErrors.drag_coefficient === null && Number(values.drag_coefficient) === 0) {
    fieldErrors.drag_coefficient = "Must be > 0 for this study (vacuum has nothing to converge)";
  }
  const steps = parseSteps(stepsText);
  const methodsError = methods.length === 0 ? "Select at least one method" : null;
  const hasErrors =
    Object.values(fieldErrors).some((e) => e !== null) || !steps.ok || methodsError !== null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors || !steps.ok) return;
    setRunning(true);
    setApiError(null);
    try {
      const parameters = Object.fromEntries(
        PARAMETER_FIELDS.map((f) => [f.name, Number(values[f.name])]),
      ) as unknown as ProjectileParameters;
      // Keep the canonical method order regardless of click order.
      const ordered = METHODS.filter((m) => methods.includes(m));
      setResult(
        await runIntegratorStudy({ parameters, dt_values: steps.values, methods: ordered }),
      );
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }

  const form = (
    <form onSubmit={onSubmit} noValidate aria-label="Study inputs">
      <fieldset>
        <legend>Physical parameters</legend>
        {PARAMETER_FIELDS.map((f) => (
          <NumberField
            key={f.name}
            field={f}
            value={values[f.name] ?? ""}
            error={touched ? (fieldErrors[f.name] ?? null) : null}
            onChange={(v) => setValues((prev) => ({ ...prev, [f.name]: v }))}
          />
        ))}
      </fieldset>
      <fieldset>
        <legend>Integrators</legend>
        {METHODS.map((m) => (
          <label key={m} className="checkbox">
            <input
              type="checkbox"
              checked={methods.includes(m)}
              onChange={(e) =>
                setMethods((prev) =>
                  e.target.checked ? [...prev, m] : prev.filter((x) => x !== m),
                )
              }
            />
            {METHOD_LABELS[m]}
          </label>
        ))}
        {touched && methodsError && <p className="field-error">{methodsError}</p>}
        <div className="field">
          <label htmlFor="field-dt">
            Time steps <span className="unit">(s, comma-separated)</span>
          </label>
          <textarea
            id="field-dt"
            rows={3}
            value={stepsText}
            aria-invalid={touched && !steps.ok}
            aria-describedby={touched && !steps.ok ? "field-dt-error" : undefined}
            onChange={(e) => setStepsText(e.target.value)}
          />
          {touched && !steps.ok && (
            <p className="field-error" id="field-dt-error">
              {steps.error}
            </p>
          )}
        </div>
      </fieldset>
      <button type="submit" disabled={running}>
        {running ? "Running…" : "Run study"}
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
          <IntegratorCharts result={result} />
        ) : (
          empty(
            "Each selected method integrates the motion over the exact flight time with every " +
              "time step you list. Errors are measured against the exact solution.",
          )
        )
      }
      results={
        result ? (
          <IntegratorOrders result={result} />
        ) : (
          empty("Fitted convergence orders appear here, next to the theoretical ones.")
        )
      }
      assumptions={
        result ? (
          <IntegratorAssumptions result={result} />
        ) : (
          empty("The study's assumptions are listed with every run.")
        )
      }
      validation={
        result ? (
          <IntegratorValidation result={result} />
        ) : (
          empty(
            "The order is fitted only over step sizes that satisfy a pre-declared rule. Every " +
              "run, and why it was included or excluded, appears here.",
          )
        )
      }
    />
  );
}
