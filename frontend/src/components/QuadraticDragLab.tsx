"use client";

import { type FormEvent, useState } from "react";

import {
  ApiError,
  type QuadraticAngleSweepResponse,
  type QuadraticDragResponse,
  type SolverSettings,
  simulateQuadraticDrag,
} from "@/lib/api/client";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import { SOLVER_FIELDS, SOLVER_METHODS } from "@/lib/projectile/fields";
import {
  QUADRATIC_PARAMETER_FIELDS,
  toQuadraticDragParameters,
} from "@/lib/projectile/quadraticFields";
import { NumberField } from "./NumberField";
import { QuadraticAngleSweepPanel, QuadraticSweepValidation } from "./QuadraticAngleSweepPanel";
import {
  QuadraticDragAssumptions,
  QuadraticDragCharts,
  QuadraticDragSummary,
  QuadraticDragValidation,
} from "./QuadraticDragResults";
import { ReferenceRunPanel } from "./ReferenceRunPanel";
import { STALE_INPUTS_NOTE, Workspace, runStatus } from "./Workspace";
import { useReferenceRun } from "./useReferenceRun";
import { useReopenedRun } from "./useReopenedRun";

type FormValues = Record<string, string>;

const ALL_FIELDS: readonly NumericFieldSpec[] = [...QUADRATIC_PARAMETER_FIELDS, ...SOLVER_FIELDS];
const INITIAL_VALUES: FormValues = Object.fromEntries(
  ALL_FIELDS.map((f) => [f.name, String(f.default)]),
);
// The page shows the simulation and, under its results, the launch-angle sweep (roadmap 2.2,
// D2). A reference run is overlaid only on runs of the same model (roadmap 1.6, decision 17).
const PAGE_MODELS = [
  "physics.projectile.quadratic_drag",
  "physics.projectile.quadratic_angle_sweep",
] as const;

export function QuadraticDragLab() {
  const [values, setValues] = useState<FormValues>(INITIAL_VALUES);
  const [method, setMethod] = useState<SolverSettings["method"]>("DOP853");
  const [touched, setTouched] = useState(false);
  const [status, setStatus] = useState<"idle" | "running">("idle");
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<QuadraticDragResponse | null>(null);
  // The result is current only while the form still matches the inputs it came from.
  const [resultKey, setResultKey] = useState<string | null>(null);
  const currentKey = JSON.stringify([values, method]);
  const referenceRun = useReferenceRun();
  // The sweep on screen, with the simulation run it was made from (its checks go under
  // Validation, and only while that run is the one shown).
  const [sweep, setSweep] = useState<{
    forRun: string;
    response: QuadraticAngleSweepResponse;
  } | null>(null);
  // The sweep's number of angles, kept here because the panel remounts with each simulation:
  // a reopened sweep's, or the last one typed; undefined until then (the contract's default).
  const [sweepAngles, setSweepAngles] = useState<string | undefined>(undefined);

  // A sweep's stored parameters have no launch angle (it does not use one): keep the current.
  const reopened = useReopenedRun(PAGE_MODELS, (run) => {
    const inputs = run.inputs as {
      parameters: Record<string, number>;
      solver: { method: SolverSettings["method"]; rtol: number; atol: number };
      n_angles?: number;
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
    if (run.model_id === "physics.projectile.quadratic_angle_sweep") {
      if (inputs.n_angles !== undefined) setSweepAngles(String(inputs.n_angles));
      return "Run the simulation, then sweep the launch angle.";
    }
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
        await simulateQuadraticDrag({
          parameters: toQuadraticDragParameters(values),
          solver: { method, rtol: num("rtol"), atol: num("atol") },
        }),
      );
      setResultKey(key);
    } catch (err) {
      // The server checks the combined rules (drag rate, atol against min(v0, v_t), a
      // resolvable flight) and says why it refused; its message is shown as it is.
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
      <fieldset>
        <legend>Physical parameters</legend>
        {QUADRATIC_PARAMETER_FIELDS.map(field)}
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
        result && <QuadraticDragCharts result={result} reference={referenceRun.response} />
      }
      results={
        result && (
          <>
            <QuadraticDragSummary result={result} />
            {/* Keyed by run, so a new simulation clears any earlier sweep. */}
            <QuadraticAngleSweepPanel
              key={result.metadata.run_id}
              parameters={result.parameters}
              solver={result.solver}
              referenceRun={referenceRun}
              initialAngles={sweepAngles}
              onAnglesChange={setSweepAngles}
              onSweep={(response) => setSweep({ forRun: result.metadata.run_id, response })}
            />
          </>
        )
      }
      assumptions={result && <QuadraticDragAssumptions result={result} />}
      validation={
        result && (
          <>
            <QuadraticDragValidation result={result} />
            {sweep?.forRun === result.metadata.run_id && (
              <QuadraticSweepValidation sweep={sweep.response} />
            )}
          </>
        )
      }
      placeholders={{
        visualisation:
          "Set the parameters and run the simulation. The trajectory (with the drag-free one), " +
          "the speed and the energy budget appear here.",
        results:
          "Flight time, range, maximum height and impact speed from the numerical solution, " +
          "the exact terminal speed, and the same launch with no drag.",
        assumptions: "The model's assumptions are listed with every run.",
        validation:
          "Quadratic drag has no exact 2-D solution, so each run is checked against what must " +
          "hold anyway (energy balance, a conserved quantity, proved bounds) and, for a " +
          "vertical launch, against the exact vertical flight.",
      }}
    />
  );
}
