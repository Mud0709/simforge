import openapi from "@/lib/api/openapi.json";

/**
 * Parsing and validation of the time-step list. As with the other forms, the bounds come
 * from the backend's OpenAPI schema; the server re-validates everything.
 */
const dtSchema = openapi.components.schemas.IntegratorStudyRequest.properties.dt_values;
export const DT_LIMITS = {
  minItems: dtSchema.minItems,
  maxItems: dtSchema.maxItems,
  min: dtSchema.items.minimum,
  max: dtSchema.items.maximum,
};

// Mirrors the backend default (0.2 s halved seven times). Kept as text for the form.
export const DEFAULT_DT_TEXT = Array.from({ length: 8 }, (_, i) => 0.2 / 2 ** i).join(", ");

export type ParsedSteps = { ok: true; values: number[] } | { ok: false; error: string };

export function parseSteps(raw: string): ParsedSteps {
  const tokens = raw.split(/[\s,;]+/).filter((t) => t !== "");
  if (tokens.length < DT_LIMITS.minItems)
    return { ok: false, error: `Enter at least ${DT_LIMITS.minItems} time steps` };
  if (tokens.length > DT_LIMITS.maxItems)
    return { ok: false, error: `At most ${DT_LIMITS.maxItems} time steps` };
  const values: number[] = [];
  for (const token of tokens) {
    const v = Number(token);
    if (!Number.isFinite(v)) return { ok: false, error: `"${token}" is not a finite number` };
    if (v < DT_LIMITS.min)
      return { ok: false, error: `Time steps must be ≥ ${DT_LIMITS.min} s (got ${token})` };
    if (v > DT_LIMITS.max) return { ok: false, error: `Time steps must be ≤ ${DT_LIMITS.max} s` };
    values.push(v);
  }
  if (new Set(values).size !== values.length)
    return { ok: false, error: "Remove duplicate time steps" };
  return { ok: true, values };
}
