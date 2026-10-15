"use client";

import type { NumericFieldSpec } from "@/lib/fields";

export function NumberField({
  field,
  value,
  error,
  onChange,
}: {
  field: NumericFieldSpec;
  value: string;
  error: string | null;
  onChange: (v: string) => void;
}) {
  const id = `field-${field.name}`;
  return (
    <div className="field">
      <label htmlFor={id}>
        {field.label} {field.unit && <span className="unit">({field.unit})</span>}
      </label>
      <input
        id={id}
        name={field.name}
        type="text"
        inputMode="decimal"
        autoComplete="off"
        value={value}
        aria-invalid={error !== null}
        aria-describedby={error ? `${id}-error` : undefined}
        title={field.description}
        onChange={(e) => onChange(e.target.value)}
      />
      {error && (
        <p className="field-error" id={`${id}-error`}>
          {error}
        </p>
      )}
    </div>
  );
}
