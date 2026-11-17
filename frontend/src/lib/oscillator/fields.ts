import type { OscillatorParameters } from "@/lib/api/client";
import { type NumericFieldSpec, spec } from "@/lib/fields";

/** The oscillator form's physical fields, with bounds and defaults from the contract. */
export const OSCILLATOR_PARAMETER_FIELDS = [
  spec("OscillatorParameters", "mass", "Mass", "kg"),
  spec("OscillatorParameters", "spring_constant", "Spring constant", "N/m"),
  spec("OscillatorParameters", "damping_coefficient", "Damping coefficient", "kg/s"),
  spec("OscillatorParameters", "drive_amplitude", "Drive amplitude", "N"),
  spec("OscillatorParameters", "drive_angular_frequency", "Drive angular frequency", "rad/s"),
  spec("OscillatorParameters", "initial_displacement", "Initial displacement", "m"),
  spec("OscillatorParameters", "initial_velocity", "Initial velocity", "m/s"),
  spec("OscillatorParameters", "duration", "Duration", "s"),
] as const satisfies readonly NumericFieldSpec[];

type ParameterName = keyof OscillatorParameters & string;

/** The request's parameters from the form's text values, field by field (checked by tsc). */
export function toOscillatorParameters(
  values: Record<string, string>,
): Required<OscillatorParameters> {
  const num = (name: ParameterName) => Number(values[name]);
  return {
    mass: num("mass"),
    spring_constant: num("spring_constant"),
    damping_coefficient: num("damping_coefficient"),
    drive_amplitude: num("drive_amplitude"),
    drive_angular_frequency: num("drive_angular_frequency"),
    initial_displacement: num("initial_displacement"),
    initial_velocity: num("initial_velocity"),
    duration: num("duration"),
  };
}

/**
 * The three presets, as the text each field takes (m = 1 kg, k = 25 N/m, so w0 = 5 rad/s).
 * Damped is the contract's defaults; Simple removes the damping; Driven drives at w0.
 */
export const PRESETS: Record<"Simple" | "Damped" | "Driven", Record<string, string>> = {
  Simple: {
    damping_coefficient: "0",
    drive_amplitude: "0",
    initial_displacement: "0.1",
    initial_velocity: "0",
  },
  Damped: {
    damping_coefficient: "0.5",
    drive_amplitude: "0",
    initial_displacement: "0.1",
    initial_velocity: "0",
  },
  Driven: {
    damping_coefficient: "0.5",
    drive_amplitude: "1",
    drive_angular_frequency: "5",
    initial_displacement: "0",
    initial_velocity: "0",
  },
};
