import { formatExp, formatSig } from "./format";

describe("formatSig", () => {
  it.each([
    [0, "0"],
    [40.78979, "40.7898"],
    [3.0, "3"],
    [-12.5, "-12.5"],
    [0.0012345678, "0.00123457"],
    [1234567, "1.23457e6"],
    [2.2e-12, "2.2e-12"],
  ])("formats %s as %s", (x, expected) => {
    expect(formatSig(x)).toBe(expected);
  });

  it("never renders non-finite values as numbers", () => {
    expect(formatSig(NaN)).toBe("—");
    expect(formatSig(Infinity)).toBe("—");
  });
});

describe("formatExp", () => {
  it.each([
    [2.2158843859748193e-12, "2.2e-12"],
    [1e-15, "1e-15"],
    [12345, "1.2e4"],
  ])("formats %s as %s", (x, expected) => {
    expect(formatExp(x)).toBe(expected);
  });
});
