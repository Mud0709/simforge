import type {
  AngleSweepResponse,
  IntegratorStudyResponse,
  ProfileResponse,
  ProjectileResponse,
  SolowResponse,
} from "@/lib/api/client";
import { toCsv } from "./csv";
import { exportTables } from "./tables";

// Small hand-made responses: only the fields the export reads. The units maps are copied by
// hand from the backend's UNITS dictionaries. Expected headers and rows are written out by
// hand, never produced by the code under test.

/** The header line and the first data line of a table's CSV. */
function headAndFirstRow(csv: string): [string, string] {
  const lines = csv.split("\r\n");
  return [lines[0]!, lines[1]!];
}

const metadata = { run_id: "0123abcd-0000-0000-0000-000000000000" };

describe("exportTables", () => {
  it("projectile: the trajectory and the energy budget, against time", () => {
    const response = {
      model: { id: "physics.projectile" },
      metadata,
      units: { t: "s", x: "m", y: "m", speed: "m/s", energy: "J" },
      series: {
        t: [0, 0.5],
        x_analytical: [0, 6.5],
        y_analytical: [0, 5.75],
        x_numerical: [0, 6.500000000000001],
        y_numerical: [0, 5.749999999999999],
        speed_numerical: [20, 17.25],
        kinetic_energy: [200, 148.78],
        potential_energy: [0, 56.4],
        drag_work: [0, -5.18],
      },
    } as unknown as ProjectileResponse;

    const tables = exportTables(response);
    expect(tables.map((t) => t.name)).toEqual(["trajectory", "energy"]);
    expect(headAndFirstRow(toCsv(tables[0]!))).toEqual([
      "t [s],x_analytical [m],y_analytical [m],x_numerical [m],y_numerical [m],speed_numerical [m/s]",
      "0,0,0,0,0,20",
    ]);
    expect(toCsv(tables[0]!).split("\r\n")[2]).toBe(
      "0.5,6.5,5.75,6.500000000000001,5.749999999999999,17.25",
    );
    expect(headAndFirstRow(toCsv(tables[1]!))).toEqual([
      "t [s],kinetic_energy [J],potential_energy [J],drag_work [J]",
      "0,200,0,0",
    ]);
    // A number cell is never prefixed, even when negative.
    expect(toCsv(tables[1]!).split("\r\n")[2]).toBe("0.5,148.78,56.4,-5.18");
  });

  it("angle sweep: range, flight time and height against launch angle", () => {
    const response = {
      model: { id: "physics.projectile.angle_sweep" },
      metadata,
      units: { angle: "deg", range: "m", flight_time: "s", max_height: "m" },
      angles_deg: [0, 45, 90],
      ranges: [0, 12.5, 0],
      flight_times: [0, 2.16, 2.5],
      max_heights: [0, 5.4, 9],
    } as unknown as AngleSweepResponse;

    const tables = exportTables(response);
    expect(tables.map((t) => t.name)).toEqual(["range_vs_angle"]);
    expect(headAndFirstRow(toCsv(tables[0]!))).toEqual([
      "angle [deg],range [m],flight_time [s],max_height [m]",
      "0,0,0,0",
    ]);
  });

  it("integrator study: every run of each method, and the plotted trajectories", () => {
    const run = (h: number, extra: Record<string, unknown> = {}) => ({
      h,
      n_steps: 10,
      kh: 0.05,
      stability: "stable",
      diverged: false,
      max_position_error: 0.012,
      max_velocity_error: 0.0006,
      final_position_error: 0.011,
      final_velocity_error: 0.0005,
      in_position_fit: false,
      in_velocity_fit: true,
      exclusion_reason: "pre-asymptotic",
      ...extra,
    });
    const response = {
      model: { id: "physics.projectile.integrators" },
      metadata,
      units: {
        h: "s",
        kh: "dimensionless",
        position_error: "m",
        velocity_error: "m/s",
        x: "m",
        y: "m",
      },
      exact_trajectory: { x: [0, 1, 2], y: [0, 0.8, 1.2] },
      results: [
        {
          method: "euler",
          runs: [run(0.25), run(0.125, { max_position_error: null, diverged: true })],
          trajectory: { h: 0.25, x: [0, 1.1], y: [0, 0.9] },
        },
        { method: "rk4", runs: [run(0.25)], trajectory: null },
      ],
    } as unknown as IntegratorStudyResponse;

    const tables = exportTables(response);
    expect(tables.map((t) => t.name)).toEqual(["runs_euler", "runs_rk4", "trajectories"]);
    expect(headAndFirstRow(toCsv(tables[0]!))).toEqual([
      "h [s],n_steps,kh [dimensionless],stability,diverged,max_position_error [m]," +
        "max_velocity_error [m/s],final_position_error [m],final_velocity_error [m/s]," +
        "in_position_fit,in_velocity_fit,exclusion_reason",
      "0.25,10,0.05,stable,false,0.012,0.0006,0.011,0.0005,false,true,pre-asymptotic",
    ]);
    // A diverged run has no error: an empty cell, not a zero.
    expect(toCsv(tables[0]!).split("\r\n")[2]).toBe(
      "0.125,10,0.05,stable,true,,0.0006,0.011,0.0005,false,true,pre-asymptotic",
    );
    // No shared x here: each trajectory is an (x, y) pair; shorter ones end in empty cells.
    const traj = toCsv(tables[2]!).split("\r\n");
    expect(traj.slice(0, 2)).toEqual([
      "exact_x [m],exact_y [m],euler_x (h = 0.25 s) [m],euler_y (h = 0.25 s) [m]",
      "0,0,0,0",
    ]);
    expect(traj[3]).toBe("2,1.2,,");
  });

  it("Solow: both paths, year by year, with the model's units", () => {
    const path = (k0: number) => ({
      capital: [k0, 3.8],
      output: [1.5, 1.52],
      consumption: [1.2, 1.21],
      investment: [0.3, 0.31],
      savings_rate: [0.2, 0.2],
      output_per_worker_index: [100, 102.5],
      output_per_worker_growth: [0.025],
    });
    const response = {
      model: { id: "economy.solow" },
      metadata,
      units: {
        years: "year",
        capital: "capital per effective worker (model units, A_0 = L_0 = 1)",
        output: "output per effective worker per year (model units)",
        consumption: "consumption per effective worker per year (model units)",
        investment: "investment per effective worker per year (model units)",
        savings_rate: "fraction of output",
        output_per_worker_index: "index, year 0 = 100",
        output_per_worker_growth: "fraction per year",
      },
      years: [0, 1],
      baseline: path(3.689),
      scenario: path(3.7),
    } as unknown as SolowResponse;

    const tables = exportTables(response);
    expect(tables.map((t) => t.name)).toEqual(["paths"]);
    const unitsOf = (p: string) =>
      `"${p}_capital [capital per effective worker (model units, A_0 = L_0 = 1)]",` +
      `${p}_output [output per effective worker per year (model units)],` +
      `${p}_consumption [consumption per effective worker per year (model units)],` +
      `${p}_investment [investment per effective worker per year (model units)],` +
      `${p}_savings_rate [fraction of output],` +
      `"${p}_output_per_worker_index [index, year 0 = 100]",` +
      `${p}_output_per_worker_growth [fraction per year]`;
    const lines = toCsv(tables[0]!).split("\r\n");
    expect(lines[0]).toBe(`year [year],${unitsOf("baseline")},${unitsOf("scenario")}`);
    expect(lines[1]).toBe("0,3.689,1.5,1.2,0.3,0.2,100,0.025,3.7,1.5,1.2,0.3,0.2,100,0.025");
    // Growth to the next year is one shorter than the years: its last cell is empty.
    expect(lines[2]).toBe("1,3.8,1.52,1.21,0.31,0.2,102.5,,3.8,1.52,1.21,0.31,0.2,102.5,");
  });

  it("dataset profile: per-column statistics only, with the user's column names guarded", () => {
    const base = {
      inferred_type: "numeric",
      overridden: false,
      missing_count: 1,
      missing_percent: 25,
      invalid_count: 0,
      invalid_percent: 0,
      valid_count: 3,
      numeric: null,
      categorical: null,
      date: null,
    };
    const response = {
      model: { id: "quant.dataset_profile" },
      metadata,
      columns: [
        {
          ...base,
          index: 0,
          name: "=SUM(A1)",
          type: "numeric",
          numeric: {
            count: 3,
            mean: -3.2,
            std: null,
            min: -5,
            q1: -4,
            median: -3,
            q3: -2.5,
            max: -2,
          },
        },
        {
          ...base,
          index: 1,
          name: "city",
          type: "categorical",
          inferred_type: "categorical",
          categorical: { count: 3, unique: 2, other_count: 0, top: [{ value: "Paris", count: 2 }] },
        },
      ],
      preview: { columns: ["=SUM(A1)", "city"], rows: [["1", "Paris"]], truncated_cells: 0 },
    } as unknown as ProfileResponse;

    const tables = exportTables(response);
    expect(tables.map((t) => t.name)).toEqual(["column_statistics"]);
    const csv = toCsv(tables[0]!);
    const lines = csv.split("\r\n");
    expect(lines[0]).toBe(
      "index,name,type,inferred_type,overridden,missing_count,missing_percent,invalid_count," +
        "invalid_percent,valid_count,numeric_count,mean,std,min,q1,median,q3,max," +
        "categorical_count,categorical_unique,categorical_other_count," +
        "date_count,date_unique,date_min,date_max,date_span_days",
    );
    expect(lines[1]).toBe(
      "0,'=SUM(A1),numeric,numeric,false,1,25,0,0,3,3,-3.2,,-5,-4,-3,-2.5,-2,,,,,,,,",
    );
    expect(lines[2]).toBe("1,city,categorical,categorical,false,1,25,0,0,3,,,,,,,,,3,2,0,,,,,");
    // Never the file's rows: no preview cell and no category value appears.
    expect(csv).not.toContain("Paris");
  });

  it("gives no tables for a model it does not know", () => {
    const response = { model: { id: "physics.unknown" }, metadata } as unknown as SolowResponse;
    expect(exportTables(response)).toEqual([]);
  });
});
