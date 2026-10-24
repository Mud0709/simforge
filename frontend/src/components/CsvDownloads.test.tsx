import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { AngleSweepResponse, ProfileResponse } from "@/lib/api/client";
import { CsvDownloads } from "./CsvDownloads";

const RESPONSE = {
  model: { id: "physics.projectile.angle_sweep" },
  metadata: { run_id: "89abcdef-0000-0000-0000-000000000000" },
  units: { angle: "deg", range: "m", flight_time: "s", max_height: "m" },
  angles_deg: [0, 90],
  ranges: [0, -0],
  flight_times: [0, 2.5],
  max_heights: [0, 9],
} as unknown as AngleSweepResponse;

afterEach(() => vi.unstubAllGlobals());

describe("CsvDownloads", () => {
  it("downloads one table as a CSV file named by model, run and table", async () => {
    const blobs: Blob[] = [];
    vi.stubGlobal("URL", {
      ...URL,
      createObjectURL: vi.fn((b: Blob) => {
        blobs.push(b);
        return "blob:fake";
      }),
      revokeObjectURL: vi.fn(),
    });
    const names: string[] = [];
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement,
    ) {
      names.push(this.download);
    });

    render(<CsvDownloads response={RESPONSE} />);
    await userEvent.click(
      screen.getByRole("button", { name: "Download range against angle (CSV)" }),
    );

    expect(names).toEqual(["physics.projectile.angle_sweep_89abcdef_range_vs_angle.csv"]);
    expect(blobs[0]!.type).toBe("text/csv;charset=utf-8");
    expect(screen.getByText(/full precision/)).toHaveTextContent(/with units in the headers/);
    expect(await blobs[0]!.text()).toBe(
      "angle [deg],range [m],flight_time [s],max_height [m]\r\n0,0,0,0\r\n90,-0,2.5,9\r\n",
    );
    click.mockRestore();
  });

  it("does not claim units for a table that has none (dataset profile)", () => {
    const profile = {
      model: { id: "quant.dataset_profile" },
      metadata: { run_id: "89abcdef-0000-0000-0000-000000000000" },
      columns: [],
    } as unknown as ProfileResponse;
    render(<CsvDownloads response={profile} />);
    expect(screen.getByText(/full precision/)).not.toHaveTextContent(/units/);
  });
});
