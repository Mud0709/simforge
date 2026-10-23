import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ExperimentLog, PAGE_SIZE } from "./ExperimentLog";

function run(i: number, extra: Record<string, unknown> = {}) {
  return {
    run_id: `run-${i}`,
    model_id: "economy.solow",
    model_version: "1.0.0",
    created_at: `2026-10-23T10:00:${String(i % 60).padStart(2, "0")}+00:00`,
    input_hash: "a".repeat(64),
    inputs: {},
    summary: {},
    environment: {},
    record_version: 2,
    output_digest: "b".repeat(64),
    replay_of: null,
    lab: "economy",
    headline: `headline ${i}`,
    ...extra,
  };
}

/** Answers each GET /experiments with `pages[n]` in turn and records the URLs asked for. */
function mockLog(...pages: unknown[][]) {
  const urls: string[] = [];
  let n = 0;
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      urls.push(url);
      const body = pages[Math.min(n++, pages.length - 1)];
      return Promise.resolve(
        new Response(JSON.stringify(body), { headers: { "Content-Type": "application/json" } }),
      );
    }),
  );
  return urls;
}

afterEach(() => vi.unstubAllGlobals());

describe("ExperimentLog", () => {
  it("shows the headline each model wrote", async () => {
    mockLog([run(1, { headline: "k* 3.689 → 6.584, half-life 12.4 y" })]);
    render(<ExperimentLog />);
    const row = await screen.findByRole("row", { name: /economy\.solow/ });
    expect(within(row).getByText("k* 3.689 → 6.584, half-life 12.4 y")).toBeInTheDocument();
  });

  it("filters by lab through the API", async () => {
    const urls = mockLog([run(1)], [run(2, { model_id: "quant.dataset_profile", lab: "quant" })]);
    render(<ExperimentLog />);
    await screen.findByText("headline 1");
    await userEvent.click(screen.getByRole("button", { name: "Quant" }));
    expect(await screen.findByText("headline 2")).toBeInTheDocument();
    expect(screen.queryByText("headline 1")).not.toBeInTheDocument();
    expect(urls.at(-1)).toContain("lab=quant");
    expect(screen.getByRole("button", { name: "Quant" })).toHaveAttribute("aria-pressed", "true");
  });

  it("loads more runs only when a full page came back", async () => {
    const full = Array.from({ length: PAGE_SIZE }, (_, i) => run(i));
    const urls = mockLog(full, [run(999)]);
    render(<ExperimentLog />);
    await screen.findByText("headline 0");
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(await screen.findByText("headline 999")).toBeInTheDocument();
    expect(screen.getByText("headline 0")).toBeInTheDocument(); // appended, not replaced
    expect(urls.at(-1)).toContain(`offset=${PAGE_SIZE}`);
    expect(screen.queryByRole("button", { name: "Load more" })).not.toBeInTheDocument();
  });

  it("marks a replay and names the run it reproduced", async () => {
    mockLog([run(2, { replay_of: "0123456789abcdef" })]);
    render(<ExperimentLog />);
    expect(await screen.findByText(/replay of 01234567/)).toBeInTheDocument();
  });

  it("says when there are no runs in a lab yet", async () => {
    mockLog([]);
    render(<ExperimentLog />);
    expect(await screen.findByText(/No saved runs/)).toBeInTheDocument();
  });
});
