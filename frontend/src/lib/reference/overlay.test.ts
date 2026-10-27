import type { ModelResponse } from "@/lib/api/client";
import { isModelResponse } from "@/lib/api/models";
import { overlayFor, referenceSeries } from "./overlay";

// Hand-made, and only the fields these functions read.
const PROJECTILE = {
  model: { id: "physics.projectile", version: "1.0.0" },
  units: { t: "s", x: "m", y: "m", energy: "J" },
  series: {
    t: [0, 1],
    x_analytical: [0, 4],
    y_analytical: [0, 0],
    x_numerical: [0, 3.5],
    y_numerical: [0, 0.5],
    kinetic_energy: [9, 9],
    potential_energy: [0, 0],
    drag_work: [0, 0],
  },
} as unknown as ModelResponse;

const QUADRATIC = {
  model: { id: "physics.projectile.quadratic_drag", version: "1.0.0" },
  units: { t: "s", x: "m", y: "m", speed: "m/s", energy: "J" },
  series: {
    t: [0, 1],
    x: [0, 3],
    y: [0, 0.25],
    speed: [10, 7.5],
    kinetic_energy: [50, 28],
    potential_energy: [0, 2.45],
    drag_work: [0, 19.55],
    vacuum_t: [0, 1, 2],
    vacuum_x: [0, 4, 8],
    vacuum_y: [0, 1, 0],
  },
} as unknown as ModelResponse;

const PROFILE = { model: { id: "quant.dataset_profile", version: "1.0.0" } } as ModelResponse;

describe("reference series", () => {
  it("names each curve and takes its units from the response's own units map", () => {
    // The projectile's numerical trajectory: what its solver computed, as are its energies.
    const [trajectory] = referenceSeries(PROJECTILE).trajectory!;
    expect(trajectory).toEqual({
      label: "numerical trajectory",
      x: { name: "x_numerical", unit: "m", values: [0, 3.5] },
      y: { name: "y_numerical", unit: "m", values: [0, 0.5] },
    });
    const energy = referenceSeries(PROJECTILE).energy!;
    expect(energy.map((s) => s.y.unit)).toEqual(["J", "J", "J"]);
    expect(energy[0]!.x).toEqual({ name: "t", unit: "s", values: [0, 1] });
  });

  it("quadratic drag: the numerical trajectory, the speed and the energies, with units", () => {
    const s = referenceSeries(QUADRATIC);
    // What the reference's solver computed; the drag-free curve depends on the inputs alone.
    expect(s.trajectory).toEqual([
      {
        label: "numerical trajectory",
        x: { name: "x", unit: "m", values: [0, 3] },
        y: { name: "y", unit: "m", values: [0, 0.25] },
      },
    ]);
    expect(s.speed).toEqual([
      {
        label: "speed",
        x: { name: "t", unit: "s", values: [0, 1] },
        y: { name: "speed", unit: "m/s", values: [10, 7.5] },
      },
    ]);
    expect(s.energy!.map((e) => [e.label, e.y.name, e.y.unit, e.y.values])).toEqual([
      ["kinetic energy", "kinetic_energy", "J", [50, 28]],
      ["potential energy", "potential_energy", "J", [0, 2.45]],
      ["work against drag", "drag_work", "J", [0, 19.55]],
    ]);
    expect(overlayFor(QUADRATIC, "physics.projectile.quadratic_drag").speed).toHaveLength(1);
    // Never over the linear model's charts (decision 17: one model only).
    expect(overlayFor(QUADRATIC, "physics.projectile")).toEqual({});
  });

  it("has no curves for a dataset profile", () => {
    expect(referenceSeries(PROFILE)).toEqual({});
  });

  it("overlays only on the same model", () => {
    expect(overlayFor(PROJECTILE, "physics.projectile").trajectory).toHaveLength(1);
    expect(overlayFor(PROJECTILE, "economy.solow")).toEqual({});
    expect(overlayFor(null, "physics.projectile")).toEqual({});
  });
});

describe("isModelResponse", () => {
  it("narrows by model id", () => {
    expect(isModelResponse(PROJECTILE, "physics.projectile")).toBe(true);
    expect(isModelResponse(PROJECTILE, "physics.projectile.angle_sweep")).toBe(false);
    expect(isModelResponse(PROFILE, "quant.dataset_profile")).toBe(true);
  });
});
