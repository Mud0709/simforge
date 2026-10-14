import { describeError } from "./client";

describe("describeError", () => {
  it("passes through string details", () => {
    expect(describeError("Use method='Radau'", 422)).toBe("Use method='Radau'");
  });

  it("formats FastAPI validation errors with field paths", () => {
    const detail = [
      { loc: ["body", "parameters", "mass"], msg: "Input should be greater than 0" },
      { loc: ["body", "parameters"], msg: "Value error, zero flight time" },
    ];
    expect(describeError(detail, 422)).toBe(
      "parameters.mass: Input should be greater than 0; parameters: zero flight time",
    );
  });

  it("falls back to the status code", () => {
    expect(describeError(undefined, 500)).toBe("Request failed with status 500");
  });
});
