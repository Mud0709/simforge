import { validateField } from "@/lib/fields";
import { OSCILLATOR_PARAMETER_FIELDS } from "./fields";

const byName = (name: string) => {
  const f = OSCILLATOR_PARAMETER_FIELDS.find((x) => x.name === name);
  if (!f) throw new Error(name);
  return f;
};

// Every bound and default below is copied by hand from OscillatorParameters in
// backend/src/simforge/physics/oscillator/schemas.py (the line is given on each row), never
// read back from the generated contract. MIN_MASS = 1e-6 is physics/projectile/schemas.py:19.
// [name, label prefix, unit, default, min, max, exclusiveMin]
const EXPECTED: [string, RegExp, string, number, number | undefined, number, number?][] = [
  ["mass", /^Mass/, "kg", 1.0, 1e-6, 1e6, undefined], // schemas.py:45 ge=MIN_MASS, le=1e6
  ["spring_constant", /^Spring constant/, "N/m", 25.0, 1e-6, 1e9, undefined], // :46-48
  ["damping_coefficient", /^Damping coefficient/, "kg/s", 0.5, 0, 1e6, undefined], // :49-54
  ["drive_amplitude", /^Drive amplitude/, "N", 0.0, 0, 1e6, undefined], // :55-60
  ["drive_angular_frequency", /^Drive angular frequency/, "rad/s", 5.0, 0, 1e4, undefined], // :61-63
  ["initial_displacement", /^Initial displacement/, "m", 0.1, -1e3, 1e3, undefined], // :64-66
  ["initial_velocity", /^Initial velocity/, "m/s", 0.0, -1e4, 1e4, undefined], // :67-69
  ["duration", /^Duration/, "s", 20.0, undefined, 1e6, 0], // :70 gt=0, le=1e6
];

describe("oscillator field specs derived from the OpenAPI contract", () => {
  it("has exactly the eight physical fields, in this order", () => {
    expect(OSCILLATOR_PARAMETER_FIELDS.map((f) => f.name)).toEqual(EXPECTED.map((e) => e[0]));
  });

  it.each(EXPECTED)(
    "%s: label, unit, default and bounds equal the backend's",
    (name, label, unit, def, min, max, exMin) => {
      const f = byName(name);
      expect(f.label).toMatch(label);
      expect(f.unit).toBe(unit);
      expect(f.default).toBe(def);
      expect(f.min).toBe(min);
      expect(f.max).toBe(max);
      expect(f.exclusiveMin).toBe(exMin);
      expect(f.description.length).toBeGreaterThan(0);
    },
  );

  it("every default passes its own validation", () => {
    for (const f of OSCILLATOR_PARAMETER_FIELDS) {
      expect(validateField(f, String(f.default))).toBeNull();
    }
  });

  it("enforces the backend's single-field limits", () => {
    expect(validateField(byName("spring_constant"), "0")).toMatch(/≥ 0.000001/);
    expect(validateField(byName("duration"), "0")).not.toBeNull(); // gt=0
    expect(validateField(byName("damping_coefficient"), "-0.1")).toMatch(/≥ 0/);
    expect(validateField(byName("initial_displacement"), "-1000")).toBeNull();
    expect(validateField(byName("initial_displacement"), "1000.5")).toMatch(/≤ 1000/);
  });
});
