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

/** GET /experiments returns `runs`; POST …/replay answers with `replay(body)`. */
function mockReplayApi(
  runs: unknown[],
  replay: (body: Record<string, unknown>) => { status: number; body: unknown },
) {
  const posts: { url: string; body: Record<string, unknown> }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      if (init?.method === "POST") {
        const body = JSON.parse(String(init.body)) as Record<string, unknown>;
        posts.push({ url, body });
        const answer = replay(body);
        return Promise.resolve(
          new Response(JSON.stringify(answer.body), {
            status: answer.status,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.resolve(
        new Response(JSON.stringify(runs), { headers: { "Content-Type": "application/json" } }),
      );
    }),
  );
  return posts;
}

function verdict(extra: Record<string, unknown> = {}) {
  return {
    original_run_id: "run-1",
    model: { id: "economy.solow", version: "1.0.0", name: "Solow", description: "" },
    verdict: "identical",
    basis: "output_digest",
    explanation: "Every output value is bit-identical (the output digests match).",
    original_output_digest: "b".repeat(64),
    replay_output_digest: "b".repeat(64),
    environment_matches: true,
    environment_differences: [],
    fields: [],
    largest_difference: null,
    metadata: { run_id: "replay-1" },
    ...extra,
  };
}

describe("replaying from the log", () => {
  it("shows the verdict next to the run, without saving by default", async () => {
    const posts = mockReplayApi([run(1)], () => ({ status: 200, body: verdict() }));
    render(<ExperimentLog />);
    const row = await screen.findByRole("row", { name: /headline 1/ });
    await userEvent.click(within(row).getByRole("button", { name: "Replay" }));
    expect(await screen.findByText(/Identical/)).toBeInTheDocument();
    expect(screen.getByText(/bit-identical/)).toBeInTheDocument();
    expect(posts[0]!.url).toBe("/api/v1/experiments/run-1/replay");
    expect(posts[0]!.body).toEqual({ save_experiment: false });
  });

  it("names the field furthest from agreement and any environment change", async () => {
    mockReplayApi([run(1)], () => ({
      status: 200,
      body: verdict({
        verdict: "within_tolerance",
        basis: "summary",
        explanation: "Every summary value agrees within its declared tolerance.",
        environment_matches: false,
        environment_differences: [{ key: "cpu", original: "Intel", replay: "AMD" }],
        largest_difference: {
          field: "final_capital",
          original: 6.539483386104942,
          replay: 6.539483386104943,
          absolute_difference: 8.9e-16,
          tolerance: { relative: 1e-12, absolute: 0, reason: "r" },
          within_tolerance: true,
        },
      }),
    }));
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByRole("button", { name: "Replay" }));
    expect(await screen.findByText(/Within tolerance/)).toBeInTheDocument();
    expect(screen.getByText(/final_capital/)).toBeInTheDocument();
    expect(screen.getByText(/Environment differs: cpu/)).toBeInTheDocument();
  });

  it("sends the file again for an uploaded dataset", async () => {
    const posts = mockReplayApi(
      [run(1, { model_id: "quant.dataset_profile", lab: "quant", replay_needs_file: true })],
      () => ({ status: 200, body: verdict() }),
    );
    render(<ExperimentLog />);
    const input = await screen.findByLabelText("Replay with file");
    await userEvent.upload(input, new File(["a,b\n1,2\n"], "data.csv", { type: "text/csv" }));
    await screen.findByText(/Identical/);
    expect(posts[0]!.body).toEqual({
      save_experiment: false,
      dataset: { content_base64: btoa("a,b\n1,2\n") },
    });
  });

  it("explains a refused replay", async () => {
    mockReplayApi([run(1)], () => ({
      status: 409,
      body: { detail: "This run used economy.solow v0.9.0; the current version is v1.0.0." },
    }));
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByRole("button", { name: "Replay" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("v0.9.0");
  });

  it("saves replays when asked", async () => {
    const posts = mockReplayApi([run(1)], () => ({ status: 200, body: verdict() }));
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByLabelText(/Save replays/));
    await userEvent.click(screen.getByRole("button", { name: "Replay" }));
    await screen.findByText(/Identical/);
    expect(posts[0]!.body).toEqual({ save_experiment: true });
  });
});

describe("naming and annotating runs", () => {
  it("shows a run's name and note as plain text", async () => {
    mockLog([run(1, { name: "Golden rule", note: "<b>not bold</b>" })]);
    const { container } = render(<ExperimentLog />);
    expect(await screen.findByText("Golden rule")).toBeInTheDocument();
    expect(screen.getByText("<b>not bold</b>")).toBeInTheDocument(); // shown, not interpreted
    expect(container.querySelector("td b")).toBeNull();
  });

  it("edits the labels in place and keeps the server's answer", async () => {
    const patches: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        if (init?.method === "PATCH") {
          const body = JSON.parse(String(init.body)) as Record<string, string>;
          patches.push({ url, body });
          return Promise.resolve(
            new Response(JSON.stringify(run(1, { name: body.name, note: body.note })), {
              headers: { "Content-Type": "application/json" },
            }),
          );
        }
        return Promise.resolve(
          new Response(JSON.stringify([run(1, { name: "Old", note: null })]), {
            headers: { "Content-Type": "application/json" },
          }),
        );
      }),
    );
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit labels" }));
    const name = screen.getByLabelText("Name");
    expect(name).toHaveValue("Old");
    await userEvent.clear(name);
    await userEvent.type(name, "Baseline");
    await userEvent.type(screen.getByLabelText("Note"), "first try");
    await userEvent.click(screen.getByRole("button", { name: "Save labels" }));
    expect(await screen.findByText("Baseline")).toBeInTheDocument();
    expect(screen.getByText("first try")).toBeInTheDocument();
    expect(patches).toEqual([
      { url: "/api/v1/experiments/run-1", body: { name: "Baseline", note: "first try" } },
    ]);
    expect(screen.queryByLabelText("Name")).not.toBeInTheDocument();
  });

  it("cancelling an edit changes nothing", async () => {
    mockLog([run(1, { name: "Old" })]);
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit labels" }));
    await userEvent.type(screen.getByLabelText("Name"), " changed");
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.getByText("Old")).toBeInTheDocument();
    expect(screen.queryByText("Old changed")).not.toBeInTheDocument();
  });

  it("limits the lengths the server accepts", async () => {
    mockLog([run(1)]);
    render(<ExperimentLog />);
    await userEvent.click(await screen.findByRole("button", { name: "Edit labels" }));
    expect(screen.getByLabelText("Name")).toHaveAttribute("maxLength", "80");
    expect(screen.getByLabelText("Note")).toHaveAttribute("maxLength", "2000");
  });
});
