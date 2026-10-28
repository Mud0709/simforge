import { reopenLink } from "./pages";

describe("reopenLink", () => {
  it("reopens each sweep on its own drag law's page", () => {
    expect(reopenLink("physics.projectile.angle_sweep", "r1")).toBe("/physics/projectile?run=r1");
    expect(reopenLink("physics.projectile.quadratic_angle_sweep", "r2")).toBe(
      "/physics/projectile/quadratic-drag?run=r2",
    );
  });

  it("has no link for a model SimForge does not have", () => {
    expect(reopenLink("physics.unknown", "r3")).toBeNull();
  });
});
