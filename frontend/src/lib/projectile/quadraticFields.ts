import type { QuadraticDragParameters } from "@/lib/api/client";
import { type NumericFieldSpec, spec } from "@/lib/fields";

/** The quadratic-drag form's physical fields, with bounds and defaults from the contract. */
export const QUADRATIC_PARAMETER_FIELDS = [
  spec("QuadraticDragParameters", "initial_speed", "Initial speed", "m/s"),
  spec("QuadraticDragParameters", "launch_angle_deg", "Launch angle", "°"),
  spec("QuadraticDragParameters", "launch_height", "Launch height", "m"),
  spec("QuadraticDragParameters", "mass", "Mass", "kg"),
  spec("QuadraticDragParameters", "drag_constant", "Drag constant c", "kg/m"),
  spec("QuadraticDragParameters", "gravity", "Gravity g", "m/s²"),
] as const satisfies readonly NumericFieldSpec[];

type ParameterName = keyof QuadraticDragParameters & string;

/** The request's parameters from the form's text values, field by field (checked by tsc). */
export function toQuadraticDragParameters(
  values: Record<string, string>,
): Required<QuadraticDragParameters> {
  const num = (name: ParameterName) => Number(values[name]);
  return {
    initial_speed: num("initial_speed"),
    launch_angle_deg: num("launch_angle_deg"),
    launch_height: num("launch_height"),
    mass: num("mass"),
    drag_constant: num("drag_constant"),
    gravity: num("gravity"),
  };
}
