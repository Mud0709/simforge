import openapi from "@/lib/api/openapi.json";

/**
 * Form fields for every lab are built from the backend's OpenAPI schema rather than
 * re-typed here, so client-side checks cannot silently drift from the server's. Client-side
 * validation is a convenience for fast feedback; the server remains the authority.
 */
type JsonSchemaProperty = {
  type?: string;
  default?: unknown;
  description?: string;
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
};

export interface NumericFieldSpec {
  name: string;
  label: string;
  unit: string;
  description: string;
  default: number;
  min?: number;
  max?: number;
  exclusiveMin?: number;
  exclusiveMax?: number;
  /** True for JSON-schema "integer" fields (e.g. a number of years). */
  integer?: boolean;
}

const schemas = openapi.components.schemas as Record<
  string,
  { properties: Record<string, JsonSchemaProperty> }
>;

export function spec(schema: string, name: string, label: string, unit: string): NumericFieldSpec {
  const prop = schemas[schema]?.properties[name];
  if (!prop || typeof prop.default !== "number") {
    throw new Error(`OpenAPI schema ${schema}.${name} is missing or has no numeric default`);
  }
  return {
    name,
    label,
    unit,
    description: prop.description ?? "",
    default: prop.default,
    min: prop.minimum,
    max: prop.maximum,
    exclusiveMin: prop.exclusiveMinimum,
    exclusiveMax: prop.exclusiveMaximum,
    ...(prop.type === "integer" ? { integer: true } : {}),
  };
}

/** Returns an error message, or null if `raw` is a valid value for `field`. */
export function validateField(field: NumericFieldSpec, raw: string): string | null {
  if (raw.trim() === "") return "Required";
  const value = Number(raw);
  if (!Number.isFinite(value)) return "Must be a finite number";
  if (field.integer && !Number.isInteger(value)) return "Must be a whole number";
  if (field.min !== undefined && value < field.min) return `Must be ≥ ${field.min}`;
  if (field.max !== undefined && value > field.max) return `Must be ≤ ${field.max}`;
  if (field.exclusiveMin !== undefined && value <= field.exclusiveMin)
    return `Must be > ${field.exclusiveMin}`;
  if (field.exclusiveMax !== undefined && value >= field.exclusiveMax)
    return `Must be < ${field.exclusiveMax}`;
  return null;
}
