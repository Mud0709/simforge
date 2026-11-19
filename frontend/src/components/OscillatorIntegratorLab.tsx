"use client";

import type { Data } from "plotly.js";
import { type FormEvent, useMemo, useState } from "react";

import {
  ApiError,
  type OscillatorIntegratorResponse,
  runOscillatorIntegrators,
} from "@/lib/api/client";
import { type NumericFieldSpec, spec, validateField } from "@/lib/fields";
import { formatExp, formatSig } from "@/lib/format";
import { parseSteps } from "@/lib/integrators/steps";
import { AssumptionsList } from "./AssumptionsList";
import { ChecksTable } from "./ChecksTable";
import { NumberField } from "./NumberField";
import { PlotlyChart } from "./PlotlyChart";
import { STALE_INPUTS_NOTE, Workspace, runStatus } from "./Workspace";
import { useReopenedRun } from "./useReopenedRun";

type Method = OscillatorIntegratorResponse["methods"][number];
const METHOD_LABELS: Record<Method, string> = {
  euler: "Euler (order 1)",
  rk4: "RK4 (order 4)",
  symplectic_euler: "Symplectic Euler (order 1)",
  velocity_verlet: "Velocity Verlet (order 2)",
};
const METHODS = Object.keys(METHOD_LABELS) as Method[];
const COLORS: Record<Method, string> = {
  euler: "#dc2626",
  rk4: "#2563eb",
  symplectic_euler: "#ea580c",
  velocity_verlet: "#16a34a",
};
const PAGE_MODELS = ["physics.oscillator.integrators"] as const;

const P = "OscillatorIntegratorParameters";
const PARAMETER_FIELDS: NumericFieldSpec[] = [
  spec(P, "mass", "Mass", "kg"),
  spec(P, "spring_constant", "Spring constant", "N/m"),
  spec(P, "initial_displacement", "Initial displacement", "m"),
  spec(P, "initial_velocity", "Initial velocity", "m/s"),
];
const R = "OscillatorIntegratorRequest";
const RUN_FIELDS: NumericFieldSpec[] = [
  spec(R, "energy_dt", "Energy time step", "s"),
  // No client-side maximum: the server refuses a too-long run and says why (e2e checks that).
  { ...spec(R, "periods", "Periods", ""), max: undefined },
];
const FIELDS = [...PARAMETER_FIELDS, ...RUN_FIELDS];
const INITIAL = Object.fromEntries(FIELDS.map((f) => [f.name, String(f.default)]));
// 0.04 s halved seven times (the plan's default: theta = w h <= 0.2 at w = 5 rad/s).
const DEFAULT_DT_TEXT = Array.from({ length: 8 }, (_, i) => 0.04 / 2 ** i).join(", ");

export function OscillatorIntegratorLab() {
  const [values, setValues] = useState(INITIAL);
  const [stepsText, setStepsText] = useState(DEFAULT_DT_TEXT);
  const [methods, setMethods] = useState<Method[]>(METHODS);
  const [touched, setTouched] = useState(false);
  const [running, setRunning] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [result, setResult] = useState<OscillatorIntegratorResponse | null>(null);
  const [resultKey, setResultKey] = useState<string | null>(null);
  const currentKey = JSON.stringify([values, stepsText, [...methods].sort()]);

  const reopened = useReopenedRun(PAGE_MODELS, (run) => {
    const inputs = run.inputs as {
      parameters: Record<string, number>;
      dt_values: number[];
      methods: Method[];
      energy_dt: number;
      periods: number;
    };
    const stored: Record<string, number | undefined> = {
      ...inputs.parameters,
      energy_dt: inputs.energy_dt,
      periods: inputs.periods,
    };
    setValues((prev) =>
      Object.fromEntries(
        Object.entries(prev).map(([k, v]) => [k, stored[k] === undefined ? v : String(stored[k])]),
      ),
    );
    setStepsText(inputs.dt_values.join(", "));
    setMethods(inputs.methods);
  });

  const fieldErrors = Object.fromEntries(
    FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );
  const steps = parseSteps(stepsText);
  const methodsError = methods.length === 0 ? "Select at least one method" : null;
  const hasErrors =
    Object.values(fieldErrors).some((e) => e !== null) || !steps.ok || methodsError !== null;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (hasErrors || !steps.ok) return;
    const key = currentKey;
    setRunning(true);
    setApiError(null);
    try {
      const num = (name: string) => Number(values[name]);
      setResult(
        await runOscillatorIntegrators({
          parameters: Object.fromEntries(PARAMETER_FIELDS.map((f) => [f.name, num(f.name)])),
          dt_values: steps.values,
          methods: METHODS.filter((m) => methods.includes(m)),
          energy_dt: num("energy_dt"),
          periods: num("periods"),
        }),
      );
      setResultKey(key);
    } catch (err) {
      setApiError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }

  const form = (
    <form onSubmit={onSubmit} noValidate aria-label="Study inputs">
      {reopened.note && <p className="note">{reopened.note}</p>}
      {reopened.error && (
        <p className="api-error" role="alert">
          {reopened.error}
        </p>
      )}
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
        {RUN_FIELDS.map((f) => (
          <NumberField
            key={f.name}
            field={f}
            value={values[f.name] ?? ""}
            error={touched ? (fieldErrors[f.name] ?? null) : null}
            onChange={(v) => setValues((prev) => ({ ...prev, [f.name]: v }))}
          />
        ))}
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

  return (
    <Workspace
      parameters={form}
      status={runStatus(running ? "running" : "idle", result)}
      staleNote={result && resultKey !== currentKey ? STALE_INPUTS_NOTE : null}
      visualisation={result && <Charts result={result} />}
      results={result && <Orders result={result} />}
      assumptions={result && <AssumptionsList assumptions={result.assumptions} />}
      validation={result && <Validation result={result} />}
      placeholders={{
        visualisation:
          "Each method integrates one period at every time step you list (errors against the " +
          "exact solution), then a long run of many periods to watch the energy.",
        results: "Fitted convergence orders and the symplectic methods' energy residuals.",
        assumptions: "The study's assumptions are listed with every run.",
        validation: "The pre-declared fit rule and the per-run checks.",
      }}
    />
  );
}

function Charts({ result }: { result: OscillatorIntegratorResponse }) {
  const convergence = useMemo<Data[]>(
    () =>
      result.results.map((m) => {
        const runs = m.runs.filter((r) => r.max_scaled_error !== null);
        return {
          x: runs.map((r) => r.h),
          y: runs.map((r) => r.max_scaled_error as number),
          name: m.method,
          mode: "lines+markers",
          line: { color: COLORS[m.method], width: 1.5 },
          marker: { color: COLORS[m.method], size: 7 },
        };
      }),
    [result],
  );
  // One closed band per method: the window maxima out, the window minima back.
  const drift = useMemo<Data[]>(
    () =>
      result.energy.map((e) => {
        const mid = e.envelope.t_start.map((t, i) => (t + (e.envelope.t_end[i] ?? t)) / 2);
        return {
          x: [...mid, ...[...mid].reverse()],
          y: [...e.envelope.hi, ...[...e.envelope.lo].reverse()],
          name: e.method,
          mode: "lines",
          fill: "toself",
          line: { color: COLORS[e.method], width: 1 },
        };
      }),
    [result],
  );
  return (
    <>
      <PlotlyChart
        title="Convergence: maximum scaled error against time step"
        data={convergence}
        layout={{
          xaxis: { title: { text: "Time step h (s)" }, type: "log" },
          yaxis: { title: { text: "Max error / amplitude scale" }, type: "log" },
        }}
      />
      <PlotlyChart
        title="Energy drift: relative energy envelope against time"
        data={drift}
        layout={{
          xaxis: { title: { text: "Time (s)" } },
          yaxis: { title: { text: "Energy / initial energy" }, type: "log" },
        }}
      />
    </>
  );
}

function Orders({ result }: { result: OscillatorIntegratorResponse }) {
  const symplectic = result.energy.filter((e) => e.modified_energy_residual !== null);
  return (
    <>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th scope="col">Method</th>
              <th scope="col">Fitted order (numerical)</th>
              <th scope="col">Theoretical order</th>
              <th scope="col">R²</th>
              <th scope="col">Points</th>
            </tr>
          </thead>
          <tbody>
            {result.results.map((m) => (
              <tr key={m.method} data-testid={`order-${m.method}`}>
                <th scope="row">{METHOD_LABELS[m.method]}</th>
                <td className="num">{m.fit ? m.fit.order.toFixed(2) : "no fit"}</td>
                <td className="num">{m.theoretical_order}</td>
                <td className="num">{m.fit ? formatSig(m.fit.r_squared, 5) : "—"}</td>
                <td className="num">{m.fit ? m.fit.n_points : 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {symplectic.length > 0 && (
        <>
          <h3>Modified-energy residual (symplectic methods)</h3>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th scope="col">Method</th>
                  <th scope="col">Residual (numerical)</th>
                </tr>
              </thead>
              <tbody>
                {symplectic.map((e) => (
                  <tr key={e.method} data-testid={`modified-energy-${e.method}`}>
                    <th scope="row">{METHOD_LABELS[e.method]}</th>
                    <td className="num">{formatExp(e.modified_energy_residual as number)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

function Validation({ result }: { result: OscillatorIntegratorResponse }) {
  const { metadata } = result;
  return (
    <>
      <ChecksTable checks={result.checks} />
      <p className="note">
        <strong>Fit rule.</strong> {result.fit_rule.description}
      </p>
      <p className="note">
        Run <code>{metadata.run_id}</code> · input hash{" "}
        <code title={metadata.input_hash}>{metadata.input_hash.slice(0, 12)}…</code> ·{" "}
        {formatSig(metadata.elapsed_ms, 3)} ms · NumPy {metadata.numpy_version}
      </p>
    </>
  );
}
