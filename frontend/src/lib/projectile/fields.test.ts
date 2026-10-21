import { PARAMETER_FIELDS, SOLVER_FIELDS, validateField } from "./fields";

const byName = (name: string) => {
  const f = [...PARAMETER_FIELDS, ...SOLVER_FIELDS].find((x) => x.name === name);
  if (!f) throw new Error(name);
  return f;
};

describe("field specs derived from the OpenAPI contract", () => {
  it("picks up backend bounds and defaults", () => {
    const mass = byName("mass");
    expect(mass.min).toBe(1e-6); // physical floor (see the backend's MIN_MASS)
    expect(mass.default).toBe(1);
    const angle = byName("launch_angle_deg");
    expect([angle.min, angle.max]).toEqual([0, 90]);
  });

  it("every default passes its own validation", () => {
    for (const f of [...PARAMETER_FIELDS, ...SOLVER_FIELDS]) {
      expect(validateField(f, String(f.default))).toBeNull();
    }
  });
});

describe("validateField", () => {
  const mass = byName("mass");
  const angle = byName("launch_angle_deg");

  it.each(["", "  ", "abc", "NaN", "Infinity", "-Infinity", "1e999"])("rejects %j", (raw) => {
    expect(validateField(mass, raw)).not.toBeNull();
  });

  it("enforces exclusive and inclusive bounds", () => {
    expect(validateField(mass, "0")).toMatch(/≥ 0.000001/);
    expect(validateField(mass, "0.000001")).toBeNull();
    expect(validateField(angle, "0")).toBeNull();
    expect(validateField(angle, "90")).toBeNull();
    expect(validateField(angle, "90.01")).toMatch(/≤ 90/);
  });

  it("accepts scientific notation", () => {
    expect(validateField(byName("rtol"), "1e-8")).toBeNull();
  });
});
