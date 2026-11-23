"use client";

import type { Data } from "plotly.js";
import { type FormEvent, useMemo, useState } from "react";

import {
  ApiError,
  type ResonanceSweepParameters,
  type ResonanceSweepResponse,
  type SolverSettings,
  runResonanceSweep,
} from "@/lib/api/client";
import { type NumericFieldSpec, validateField } from "@/lib/fields";
import { formatSig } from "@/lib/format";
import { RESONANCE_SWEEP_FIELDS, RESONANCE_SWEEP_METHODS } from "@/lib/oscillator/fields";
import { AssumptionsList } from "./AssumptionsList";
import { ChecksTable } from "./ChecksTable";
import { CsvDownloads } from "./CsvDownloads";
import { NumberField } from "./NumberField";
import { PlotlyChart } from "./PlotlyChart";
import { Reproducibility } from "./Reproducibility";

/** The inputs a saved sweep stores (`inputs=` in backend/.../routes/oscillator.py). */
export interface StoredSweepInputs {
  parameters: ResonanceSweepParameters;
  solver: SolverSettings;
  n_frequencies: number;
}

const NUMERICAL = "#ea580c";
const EXACT = "#2563eb";
const ID_PREFIX = "sweep-";

/** A number with its unit, or "none" and the reason it does not exist (null is never 0). */
const exactValue = (x: number | null, unit: string) =>
  x === null ? "none: no peak when ζ ≥ 1/√2" : `${formatSig(x, 6)} ${unit}`;

/** The text each field starts with: the contract's defaults, then a reopened run's inputs. */
function initialValues(stored?: StoredSweepInputs): Record<string, string> {
  const given: Record<string, number | undefined> = {
    ...stored?.parameters,
    n_frequencies: stored?.n_frequencies,
    rtol: stored?.solver.rtol,
    atol: stored?.solver.atol,
  };
  return Object.fromEntries(
    RESONANCE_SWEEP_FIELDS.map((f) => [f.name, String(given[f.name] ?? f.default)]),
  );
}

/**
 * The simulated resonance curve (roadmap 2.5): the lock-in amplitude of a driven, damped
 * oscillator at each drive frequency, against the exact formula. It has its own form and run
 * button: it does not read the simulation beside it. `reopened` fills the form from a saved run.
 */
export function ResonanceSweepPanel({ reopened }: { reopened?: StoredSweepInputs }) {
  const [values, setValues] = useState(() => initialValues(reopened));
  const [method, setMethod] = useState<SolverSettings["method"]>(
    reopened?.solver.method ?? "DOP853",
  );
  const [touched, setTouched] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sweep, setSweep] = useState<ResonanceSweepResponse | null>(null);

  const errors = Object.fromEntries(
    RESONANCE_SWEEP_FIELDS.map((f) => [f.name, validateField(f, values[f.name] ?? "")]),
  );

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setTouched(true);
    if (Object.values(errors).some((m) => m !== null)) return;
    const num = (name: string) => Number(values[name]);
    setRunning(true);
    setError(null);
    try {
      setSweep(
        await runResonanceSweep({
          parameters: {
            mass: num("mass"),
            spring_constant: num("spring_constant"),
            damping_coefficient: num("damping_coefficient"),
            drive_amplitude: num("drive_amplitude"),
            omega_min: num("omega_min"),
            omega_max: num("omega_max"),
            settle_tolerance: num("settle_tolerance"),
          },
          solver: { method, rtol: num("rtol"), atol: num("atol") },
          n_frequencies: num("n_frequencies"),
        }),
      );
    } catch (err) {
      // The server checks the combined rules (range, damping, budget) and says why it refused.
      setError(err instanceof ApiError ? err.message : "Unexpected error");
    } finally {
      setRunning(false);
    }
  }

  const field = (f: NumericFieldSpec) => (
    <NumberField
      key={f.name}
      field={f}
      idPrefix={ID_PREFIX}
      value={values[f.name] ?? ""}
      error={touched ? (errors[f.name] ?? null) : null}
      onChange={(v) => setValues((prev) => ({ ...prev, [f.name]: v }))}
    />
  );

  const data = useMemo<Data[]>(() => {
    if (!sweep) return [];
    const { peak: p, resonance: curve } = sweep;
    return [
      {
        x: curve.angular_frequency,
        y: curve.amplitude,
        name: "Exact amplitude (formula)",
        mode: "lines",
        line: { color: EXACT, width: 2, dash: "dash" },
      },
      {
        x: sweep.angular_frequencies,
        y: sweep.amplitudes,
        name: `Simulated amplitude (numerical, ${sweep.solver.method})`,
        mode: "markers",
        marker: { color: NUMERICAL, size: 7 },
      },
      {
        x: [p.angular_frequency],
        y: [p.amplitude],
        name: "Refined peak (numerical)",
        mode: "markers",
        marker: { color: "#dc2626", size: 11 },
      },
      ...(p.exact_angular_frequency !== null && p.exact_amplitude !== null
        ? [
            {
              x: [p.exact_angular_frequency],
              y: [p.exact_amplitude],
              name: "Exact peak ω_r (formula)",
              mode: "markers",
              marker: { color: EXACT, size: 10, symbol: "diamond-open" },
            } satisfies Data,
          ]
        : []),
    ];
  }, [sweep]);

  const rows = sweep && [
    [
      "Refined peak frequency (numerical)",
      "peak-frequency",
      sweep.peak.uncertainty === null
        ? `${formatSig(sweep.peak.angular_frequency, 6)} rad/s`
        : `${formatSig(sweep.peak.angular_frequency, 6)} ± ${formatSig(sweep.peak.uncertainty, 1)} rad/s (estimate)`,
    ],
    [
      "Refined peak amplitude (numerical)",
      "peak-amplitude",
      `${formatSig(sweep.peak.amplitude, 6)} m`,
    ],
    [
      "Exact peak frequency ω_r (formula)",
      "exact-peak-frequency",
      exactValue(sweep.peak.exact_angular_frequency, "rad/s"),
    ],
    [
      "Exact peak amplitude A_max (formula)",
      "exact-peak-amplitude",
      exactValue(sweep.peak.exact_amplitude, "m"),
    ],
    [
      "Grid step ÷ damping rate γ (formula)",
      "grid-step-over-gamma",
      formatSig(sweep.grid_step_over_gamma, 6),
    ],
    [
      "Solver work, right-hand-side evaluations (numerical)",
      "n-rhs-evaluations",
      String(sweep.n_rhs_evaluations),
    ],
  ];

  return (
    <section className="card" aria-labelledby="resonance-sweep-heading">
      <h2 id="resonance-sweep-heading">Simulated resonance curve</h2>
      <p className="note">
        Drive a damped oscillator at each frequency in a range, wait for the transient to die away,
        and measure the steady amplitude. The dashed curve is the exact formula; the points are the
        solver&apos;s. This form is separate from the simulation above.
      </p>
      <form onSubmit={onSubmit} noValidate aria-label="Resonance sweep inputs">
        <fieldset>
          <legend>Oscillator and drive</legend>
          {RESONANCE_SWEEP_FIELDS.slice(0, 4).map(field)}
        </fieldset>
        <fieldset>
          <legend>Frequencies and settling</legend>
          {RESONANCE_SWEEP_FIELDS.slice(4, 8).map(field)}
        </fieldset>
        <fieldset>
          <legend>Numerical solver</legend>
          <div className="field">
            <label htmlFor="sweep-method">Sweep solver method</label>
            <select
              id="sweep-method"
              value={method}
              onChange={(e) => setMethod(e.target.value as SolverSettings["method"])}
            >
              {RESONANCE_SWEEP_METHODS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
          {RESONANCE_SWEEP_FIELDS.slice(8).map(field)}
        </fieldset>
        <button type="submit" disabled={running}>
          {running ? "Sweeping…" : "Sweep drive frequency"}
        </button>
        {error && (
          <p className="api-error" role="alert">
            {error}
          </p>
        )}
      </form>
      {sweep && rows && (
        <>
          <dl className="stats">
            {rows.map(([label, id, text]) => (
              <div key={id}>
                <dt>{label}</dt>
                <dd data-testid={id}>{text}</dd>
              </div>
            ))}
          </dl>
          <p className="note">{sweep.peak.uncertainty_note}</p>
          <PlotlyChart
            title="Simulated resonance curve: amplitude against drive frequency"
            data={data}
            layout={{
              xaxis: { title: { text: "Drive angular frequency ω (rad/s)" } },
              yaxis: { title: { text: "Amplitude A (m)" }, rangemode: "tozero" },
            }}
          />
          <ChecksTable checks={sweep.checks} />
          <AssumptionsList assumptions={sweep.assumptions} />
          <CsvDownloads response={sweep} />
          <Reproducibility metadata={sweep.metadata} />
        </>
      )}
    </section>
  );
}
