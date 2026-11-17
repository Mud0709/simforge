"use client";

import type { Data } from "plotly.js";
import { memo, useMemo } from "react";

import type { ModelResponse, OscillatorResponse } from "@/lib/api/client";
import { formatExp, formatSig } from "@/lib/format";
import { overlayFor, referenceTraces } from "@/lib/reference/overlay";
import { AssumptionsList } from "./AssumptionsList";
import { ChecksTable } from "./ChecksTable";
import { CsvDownloads } from "./CsvDownloads";
import { PlotlyChart } from "./PlotlyChart";
import { Reproducibility } from "./Reproducibility";

const NUMERICAL = "#ea580c";
const EXACT = "#2563eb";
const MODEL_ID = "physics.oscillator";

type Props = { result: OscillatorResponse };

/** A number with its unit, or "none" and the reason it does not exist (null is never 0). */
function value(x: number | null, unit: string, why: string): string {
  return x === null ? `none: ${why}` : `${formatSig(x, 8)} ${unit}`.trim();
}

/** Visualisation: displacement (numerical, exact, envelope), the energy, the resonance curve. */
function OscillatorChartsView({
  result,
  reference = null,
}: Props & { reference?: ModelResponse | null }) {
  const { series, solver, resonance, steady_state: ss, parameters } = result;
  const overlay = useMemo(() => overlayFor(reference, MODEL_ID), [reference]);

  const displacement = useMemo<Data[]>(() => {
    const traces: Data[] = [
      ...referenceTraces(overlay.displacement),
      {
        x: series.t,
        y: series.x,
        name: `Displacement (numerical, ${solver.method})`,
        mode: "lines",
        line: { color: NUMERICAL, width: 2 },
      },
      {
        x: series.t,
        y: series.x_exact,
        name: "Exact (formula)",
        mode: "lines",
        line: { color: EXACT, width: 2, dash: "dash" },
      },
    ];
    if (series.envelope) {
      const envelope = series.envelope;
      const style = { color: "#64748b", width: 1, dash: "dot" } as const;
      traces.push(
        {
          x: series.t,
          y: envelope,
          name: "Envelope +R e^(−γt) (formula)",
          mode: "lines",
          line: style,
        },
        {
          x: series.t,
          y: envelope.map((e) => -e),
          name: "Envelope −R e^(−γt) (formula)",
          mode: "lines",
          line: style,
        },
      );
    }
    return traces;
  }, [series, solver.method, overlay]);

  const energy = useMemo<Data[]>(
    () => [
      ...referenceTraces(overlay.energy),
      { x: series.t, y: series.kinetic_energy, name: "Kinetic", mode: "lines" },
      { x: series.t, y: series.potential_energy, name: "Potential", mode: "lines" },
      { x: series.t, y: series.damping_work, name: "Work done against damping", mode: "lines" },
      { x: series.t, y: series.drive_work, name: "Work done by the drive", mode: "lines" },
    ],
    [series, overlay],
  );

  const resonanceData = useMemo<Data[]>(() => {
    if (!resonance) return [];
    const traces: Data[] = [
      {
        x: resonance.angular_frequency,
        y: resonance.amplitude,
        name: "Amplitude (formula)",
        mode: "lines",
        line: { color: NUMERICAL, width: 2 },
      },
      {
        x: resonance.angular_frequency,
        y: resonance.phase_lag,
        name: "Phase lag (formula)",
        mode: "lines",
        yaxis: "y2",
        line: { color: EXACT, width: 2, dash: "dash" },
      },
    ];
    if (ss) {
      traces.push({
        x: [parameters.drive_angular_frequency ?? 0],
        y: [ss.amplitude],
        name: "This run",
        mode: "markers",
        marker: { color: "#dc2626", size: 10 },
      });
    }
    return traces;
  }, [resonance, ss, parameters.drive_angular_frequency]);

  return (
    <>
      <h3>Displacement</h3>
      <PlotlyChart
        title="Displacement against time"
        data={displacement}
        layout={{
          xaxis: { title: { text: "t (s)" } },
          yaxis: { title: { text: "x (m)" } },
        }}
      />
      <p className="note">
        The solid curve is numerical; the dashed curve is the exact solution from its formula.
        {series.envelope
          ? " The dotted curves are the envelope ±R e^(−γt) the underdamped oscillation fits inside."
          : " There is no envelope: it exists only for an underdamped oscillator."}
      </p>

      <h3>Energy budget</h3>
      <PlotlyChart
        title="Energy against time"
        data={energy}
        layout={{
          xaxis: { title: { text: "t (s)" } },
          yaxis: { title: { text: "Energy (J)" } },
        }}
      />
      <p className="note">
        Kinetic + potential + work done against damping − work done by the drive stays equal to the
        starting energy; any drift is numerical error.
      </p>

      <h3>Resonance</h3>
      {resonance ? (
        <>
          <PlotlyChart
            title="Resonance: steady-state amplitude and phase against drive frequency"
            data={resonanceData}
            layout={{
              xaxis: { title: { text: "Drive angular frequency ω (rad/s)" } },
              yaxis: { title: { text: "Amplitude A (m)" }, rangemode: "tozero" },
              yaxis2: {
                title: { text: "Phase lag δ (rad)" },
                overlaying: "y",
                side: "right",
                range: [0, Math.PI],
              },
            }}
          />
          <p className="note">
            Both curves are from the exact steady-state formulas. The marker is this run&apos;s
            drive frequency and its steady-state amplitude.
          </p>
        </>
      ) : (
        <p className="note">
          The resonance curve needs a drive and some damping: set a drive amplitude and a damping
          coefficient above zero. Without damping the amplitude at resonance has no finite value.
        </p>
      )}
    </>
  );
}

/** Results: every number is labelled numerical, exact or formula (null is shown as none). */
export function OscillatorSummary({ result }: Props) {
  const { derived: d, steady_state: ss, numerical: n } = result;
  const rows: [string, string][] = [
    ["Natural angular frequency ω₀ (formula)", value(d.natural_angular_frequency, "rad/s", "")],
    ["Damping rate γ (formula)", value(d.damping_rate, "1/s", "")],
    ["Damping ratio ζ (formula)", value(d.damping_ratio, "", "")],
    ["Quality factor Q (formula)", value(d.quality_factor, "", "no damping")],
    ["Regime (exact)", d.regime.replace("_", " ")],
    [
      "Damped angular frequency ω_d (formula)",
      value(d.damped_angular_frequency, "rad/s", "it does not oscillate"),
    ],
    ["Overdamped rate β (formula)", value(d.overdamped_rate, "1/s", "not overdamped")],
    ["Damped period T_d (formula)", value(d.damped_period, "s", "it does not oscillate")],
    [
      "Steady-state amplitude A (formula)",
      value(ss?.amplitude ?? null, "m", "undriven or undamped"),
    ],
    ["Phase lag δ (formula)", value(ss?.phase_lag ?? null, "rad", "undriven or undamped")],
    [
      "Amplitude peak at ω_r (formula)",
      value(ss?.peak_angular_frequency ?? null, "rad/s", "no peak for this damping"),
    ],
    [
      "Peak amplitude A_max (formula)",
      value(ss?.peak_amplitude ?? null, "m", "no peak for this damping"),
    ],
    ["Final displacement (numerical)", value(n.final_displacement, "m", "")],
    ["Final velocity (numerical)", value(n.final_velocity, "m/s", "")],
  ];
  return (
    <>
      <dl className="stats">
        {rows.map(([label, v]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{v}</dd>
          </div>
        ))}
      </dl>
      <p className="note">
        {result.method_note}, {n.method}, rtol = {String(n.rtol)}, atol = {String(n.atol)}
      </p>
      <p className="note">
        Formulas are exact expressions of the inputs; numerical values come from the solver.
      </p>
      <CsvDownloads response={result} />
    </>
  );
}

/** Validation: the per-run checks, the diagnostics, the record. */
export function OscillatorValidation({ result }: Props) {
  const { diagnostics: g, numerical, metadata } = result;
  const none = (x: number | null) => (x === null ? "none" : formatExp(x));
  return (
    <>
      <ChecksTable checks={result.checks} />
      <dl className="stats">
        <div>
          <dt>Max displacement error</dt>
          <dd>{formatExp(g.max_displacement_error)} × X</dd>
        </div>
        <div>
          <dt>Max velocity error</dt>
          <dd>{formatExp(g.max_velocity_error)} × ω₀X</dd>
        </div>
        <div>
          <dt>Max energy-balance residual</dt>
          <dd>{formatExp(g.max_energy_balance_residual)} × kX²</dd>
        </div>
        <div>
          <dt>Free-decay period residual</dt>
          <dd>{none(g.free_decay_period_residual)}</dd>
        </div>
        <div>
          <dt>Free-decay ratio residual</dt>
          <dd>{none(g.free_decay_ratio_residual)}</dd>
        </div>
        <div>
          <dt>Transient left at the end</dt>
          <dd>{none(g.remaining_transient)}</dd>
        </div>
        <div>
          <dt>Solver work</dt>
          <dd>
            {numerical.n_steps} steps, {numerical.n_rhs_evaluations} evaluations
          </dd>
        </div>
      </dl>
      <Reproducibility metadata={metadata} />
    </>
  );
}

/** Assumptions: what the model takes as given. */
export function OscillatorAssumptions({ result }: Props) {
  return (
    <>
      <p className="note">
        {result.model.name} · v{result.model.version}
      </p>
      <AssumptionsList assumptions={result.assumptions} />
    </>
  );
}

/** Memoised: the charts redraw only when the result (or the reference) changes. */
export const OscillatorCharts = memo(OscillatorChartsView);
