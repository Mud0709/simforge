import { keyResult } from "./ExperimentLog";

describe("keyResult", () => {
  it("summarises a projectile run", () => {
    expect(
      keyResult("physics.projectile", {
        analytical: { range: 36.3885591 },
        comparison: { max_position_error: 2.2e-11 },
      }),
    ).toBe("range 36.3886 m, error 2.2e-11 m");
  });

  it("summarises an integrator study, including methods without a fit", () => {
    expect(
      keyResult("physics.projectile.integrators", {
        methods: { euler: { position_order: 1.0089 }, rk4: { position_order: null } },
      }),
    ).toBe("euler p≈1.01, rk4 p≈n/a");
  });
});
