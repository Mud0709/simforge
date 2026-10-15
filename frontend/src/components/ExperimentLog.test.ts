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

  it("summarises a Solow run", () => {
    expect(
      keyResult("economy.solow", {
        baseline_steady_state_capital: 3.689237466703935,
        scenario_steady_state_capital: 6.584086866307975,
        half_life_years: 12.369823364170164,
      }),
    ).toBe("k* 3.689 → 6.584, half-life 12.4 y");
  });
});
