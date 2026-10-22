import type { ProjectileParameters, SolverSettings } from "@/lib/api/client";
import { type NumericFieldSpec, spec } from "@/lib/fields";

export const PARAMETER_FIELDS = [
  spec("ProjectileParameters", "initial_speed", "Initial speed", "m/s"),
  spec("ProjectileParameters", "launch_angle_deg", "Launch angle", "°"),
  spec("ProjectileParameters", "launch_height", "Launch height", "m"),
  spec("ProjectileParameters", "mass", "Mass", "kg"),
  spec("ProjectileParameters", "drag_coefficient", "Drag coefficient b", "kg/s"),
  spec("ProjectileParameters", "gravity", "Gravity g", "m/s²"),
] as const satisfies readonly NumericFieldSpec[];

export const SOLVER_FIELDS = [
  spec("SolverSettings", "rtol", "Relative tolerance", ""),
  spec("SolverSettings", "atol", "Absolute tolerance", ""),
] as const satisfies readonly NumericFieldSpec[];

export const SOLVER_METHODS: SolverSettings["method"][] = ["DOP853", "RK45", "Radau"];

export type ParameterName = keyof ProjectileParameters & string;

/**
 * The request's parameters from the form's text values, written out field by field so tsc
 * checks every name against the generated contract.
 */
export function toProjectileParameters(values: Record<string, string>): ProjectileParameters {
  const num = (name: ParameterName) => Number(values[name]);
  return {
    initial_speed: num("initial_speed"),
    launch_angle_deg: num("launch_angle_deg"),
    launch_height: num("launch_height"),
    mass: num("mass"),
    drag_coefficient: num("drag_coefficient"),
    gravity: num("gravity"),
  };
}
