"use client";

import { type FormEvent, useState } from "react";

import {
  ApiError,
  type OscillatorResponse,
  type SolverSettings,
  simulateOscillator,
} from "@/lib/api/client";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import {
  OSCILLATOR_PARAMETER_FIELDS,
  PRESETS,
  toOscillatorParameters,
} from "@/lib/oscillator/fields";
import { SOLVER_FIELDS, SOLVER_METHODS } from "@/lib/projectile/fields";
import { NumberField } from "./NumberField";
import {
  OscillatorAssumptions,
  OscillatorCharts,
  OscillatorSummary,
  OscillatorValidation,
} from "./OscillatorResults";
import { ReferenceRunPanel } from "./ReferenceRunPanel";
import { STALE_INPUTS_NOTE, Workspace, runStatus } from "./Workspace";
import { useReferenceRun } from "./useReferenceRun";
import { useReopenedRun } from "./useReopenedRun";

type FormValues = Record<string, string>;

const ALL_FIELDS: readonly NumericFieldSpec[] = [...OSCILLATOR_PARAMETER_FIELDS, ...SOLVER_FIELDS];
const INITIAL_VALUES: FormValues = Object.fromEntries(
  ALL_FIELDS.map((f) => [f.name, String(f.default)]),
);
// A preset sets every physical field: the contract's defaults, then its own changes.
const PHYSICAL_DEFAULTS = Object.fromEntries(
  OSCILLATOR_PARAMETER_FIELDS.map((f) => [f.name, String(f.default)]),
);
const PAGE_MODELS = ["physics.oscillator"] as const;

export function OscillatorLab() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [method, setMethod] = useState<SolverSettings["method"]>("DOP853");
  const [touched, setTouched] = useState(false);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<OscillatorResponse | null>(null);
  // The result is current only while the form still matches the inputs it came from.
  const [resultKey, setResultKey] = useState<string | null>(null);
  const currentKey = JSON.stringify([values, method]);
  const referenceRun = useReferenceRun();

  const reopened = useReopenedRun(PAGE_MODELS, (run) => {
    const inputs = run.inputs as {
      parameters: Record<string, number>;
      solver: { method: SolverSettings["method"]; rtol: number; atol: number };
    };
    const stored: Record<string, number | undefined> = {
      ...inputs.parameters,
      rtol: inputs.solver.rtol,
      atol: inputs.solver.atol,
    };
    setValues((prev) =>
      Object.fromEntries(
        Object.entries(prev).map(([k, v]) => [k, stored[k] === undefined ? v : String(stored[k])]),
      ),
    );
    setMethod(inputs.solver.method);
  });

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
        await simulateOscillator({
          parameters: toOscillatorParameters(values),
          solver: { method, rtol: num("rtol"), atol: num("atol") },
        }),
      );
      setResultKey(key);
    } catch (err) {
      // The server checks the combined rules (drive frequency, tolerances) and says why it
      // refused; its message is shown as it is.
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
      {reopened.note && <p className="note">{reopened.note}</p>}
      {reopened.error && (
        <p className="api-error" role="alert">
          {reopened.error}
        </p>
      )}
      <div className="presets" role="group" aria-label="Presets">
        {(Object.keys(PRESETS) as (keyof typeof PRESETS)[]).map((name) => (
          <button
            key={name}
            type="button"
            onClick={() =>
              setValues((prev) => ({ ...prev, ...PHYSICAL_DEFAULTS, ...PRESETS[name] }))
            }
          >
            {name}
          </button>
        ))}
      </div>
      <fieldset>
        <legend>Physical parameters</legend>
        {OSCILLATOR_PARAMETER_FIELDS.map(field)}
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
      reference={
        (result || referenceRun.reference) && (
          <ReferenceRunPanel run={referenceRun} current={result} modelIds={PAGE_MODELS} />
        )
      }
      visualisation={
        result && <OscillatorCharts result={result} reference={referenceRun.response} />
      }
      results={result && <OscillatorSummary result={result} />}
      assumptions={result && <OscillatorAssumptions result={result} />}
      validation={result && <OscillatorValidation result={result} />}
      placeholders={{
        visualisation:
          "Set the parameters (or pick a preset) and run the simulation. The displacement, the " +
          "energy budget and, for a driven run, the resonance curve appear here.",
        results:
          "The natural frequency, damping and regime (formulas), the steady state of a driven " +
          "run, and the final state from the numerical solution.",
        assumptions: "The model's assumptions are listed with every run.",
        validation:
          "Each run is checked against the exact solution and the energy balance, and the " +
          "numerical cost is reported.",
      }}
    />
  );
}
