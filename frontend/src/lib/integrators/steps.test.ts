import { DEFAULT_DT_TEXT, DT_LIMITS, parseSteps } from "./steps";

describe("parseSteps", () => {
  it("reads limits from the OpenAPI contract", () => {
    expect(DT_LIMITS).toEqual({ minItems: 2, maxItems: 12, exclusiveMin: 0, max: 100 });
  });

  it("parses the default list", () => {
    const r = parseSteps(DEFAULT_DT_TEXT);
    expect(r.ok && r.values).toEqual([0.2, 0.1, 0.05, 0.025, 0.0125, 0.00625, 0.003125, 0.0015625]);
  });

  it("accepts commas, spaces and scientific notation", () => {
    const r = parseSteps("1e-2;  5e-3\n0.0025");
    expect(r.ok && r.values).toEqual([0.01, 0.005, 0.0025]);
  });

  it.each([
    ["", /at least 2/],
    ["0.1", /at least 2/],
    ["0.1, 0", /> 0/],
    ["0.1, -0.05", /> 0/],
    ["0.1, NaN", /finite/],
    ["0.1, Infinity", /finite/],
    ["0.1, abc", /finite/],
    ["0.1, 101", /≤ 100/],
    ["0.1, 0.1", /duplicate/],
    [Array.from({ length: 13 }, (_, i) => 0.1 / (i + 1)).join(","), /At most 12/],
  ])("rejects %j", (raw, message) => {
    const r = parseSteps(raw);
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(message);
  });
});
