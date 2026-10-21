import { describe, expect, it } from "vitest";

import { binGeometry } from "./histogram";

const MAX = Number.MAX_VALUE;

describe("binGeometry", () => {
  it("gives centres and widths of ordinary bins", () => {
    expect(binGeometry([0, 2, 4])).toEqual({ centres: [1, 3], widths: [2, 2] });
  });

  it("does not overflow for edges near the largest double", () => {
    // (a + b) / 2 would be Infinity here; the backend's edges are finite.
    const { centres, widths } = binGeometry([1e308, 1.35e308, 1.7e308]);
    expect(centres.every(Number.isFinite)).toBe(true);
    expect(centres[0]).toBeCloseTo(1.175e308, -300);
    expect(widths.every(Number.isFinite)).toBe(true);
  });

  it("keeps the tiniest (subnormal) values instead of rounding them to 0", () => {
    const tiny = 5e-324;
    expect(binGeometry([tiny, tiny])).toEqual({ centres: [tiny], widths: [1] });
  });

  it("handles the widest bins the backend can produce", () => {
    // From -MAX to MAX the backend uses at least two bins, each MAX wide.
    const { centres, widths } = binGeometry([-MAX, 0, MAX]);
    expect(centres).toEqual([-MAX / 2, MAX / 2]);
    expect(widths).toEqual([MAX, MAX]);
  });

  it("gives a constant column's single bin a unit width", () => {
    expect(binGeometry([7, 7])).toEqual({ centres: [7], widths: [1] });
  });
});
