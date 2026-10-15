import type { ProjectileParameters, SolverSettings } from "@/lib/api/client";
import { type NumericFieldSpec, spec } from "@/lib/fields";

// The generic helpers now live in lib/fields.ts (shared by every lab); re-exported here so
// existing imports keep working.
export { type NumericFieldSpec, validateField } from "@/lib/fields";

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
