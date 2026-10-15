import { ALL_SOLOW_FIELDS } from "./economy/solowFields";
import { validateField } from "./fields";

const byName = (name: string) => {
  const f = ALL_SOLOW_FIELDS.find((x) => x.name === name);
  if (!f) throw new Error(name);
  return f;
};

describe("Solow fields derived from the OpenAPI contract", () => {
  it("picks up bounds, defaults and integer types", () => {
    const alpha = byName("capital_share");
    expect([alpha.min, alpha.max, alpha.default]).toEqual([0.05, 0.95, 0.3]);
    expect(byName("horizon_years").integer).toBe(true);
    expect(byName("savings_rate").integer).toBeUndefined();
  });

  it("every default passes its own validation", () => {
    for (const f of ALL_SOLOW_FIELDS) expect(validateField(f, String(f.default))).toBeNull();
  });

  it("enforces whole numbers only for integer fields", () => {
    expect(validateField(byName("policy_year"), "3.5")).toBe("Must be a whole number");
    expect(validateField(byName("policy_year"), "3")).toBeNull();
    expect(validateField(byName("savings_rate"), "0.25")).toBeNull();
  });
});
