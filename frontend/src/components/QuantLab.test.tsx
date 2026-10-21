import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import type { ProfileResponse } from "@/lib/api/client";
import { MAX_FILE_BYTES } from "@/lib/quant/upload";
import PROFILE from "./fixtures/messySurveyProfile.json";
import { QuantLab } from "./QuantLab";

// Plotly needs a real browser; charts are covered by the E2E test.
vi.mock("./PlotlyChart", () => ({
  PlotlyChart: ({ title }: { title: string }) => <div role="img" aria-label={title} />,
}));

const SAMPLES = [
  { id: "lab_measurements", title: "Lab measurements (clean)", description: "Clean." },
  { id: "messy_survey", title: "Survey (deliberately messy)", description: "Messy." },
];

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

/** Routes the two endpoints; `profile` decides each profile response. */
function mockApi(profile: (body: Record<string, unknown>) => Response) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith("/quant/datasets/samples")) return json(200, SAMPLES);
    return profile(JSON.parse(String(init?.body)) as Record<string, unknown>);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const profileCalls = (m: ReturnType<typeof mockApi>) =>
  m.mock.calls.filter(([url]) => String(url).endsWith("/profile"));

const region = (name: string) => screen.getByRole("region", { name });

afterEach(() => vi.unstubAllGlobals());

describe("QuantLab", () => {
  it("lays out the five workspace sections before any profile", () => {
    mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
      expect(region(name)).toBeInTheDocument();
    }
  });

  it("profiles a sample and puts each part of the profile in its section", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));

    const results = region("Results");
    expect(await within(results).findByTestId("profile-rows")).toHaveTextContent("10");
    expect(within(results).getByTestId("profile-columns")).toHaveTextContent("6");
    expect(within(results).getByTestId("profile-missing")).toHaveTextContent("7 of 60 (11.7%)");
    expect(within(results).getByTestId("profile-duplicates")).toHaveTextContent("1");
    expect(within(results).getByText(/rows 3, 7/)).toBeInTheDocument();
    expect(within(results).getByTestId("column-1")).toHaveTextContent("3 (30.0%)");
    expect(within(results).getByTestId("numeric-1")).toHaveTextContent("38.2857");
    expect(within(results).getByTestId("column-notes")).toHaveTextContent("'NA' ×2");
    expect(within(results).getByText(/Descriptive summary/)).toBeInTheDocument();

    const vis = region("Visualisation");
    expect(
      within(vis).getByRole("img", { name: /Missing and invalid values/ }),
    ).toBeInTheDocument();
    expect(within(vis).getByRole("img", { name: "Distribution of age" })).toBeInTheDocument();
    await userEvent.selectOptions(within(vis).getByLabelText("Column to plot"), "2");
    expect(within(vis).getByRole("img", { name: "Distribution of country" })).toBeInTheDocument();

    expect(within(region("Assumptions")).getByText(/Namibia/)).toBeInTheDocument();
    const validation = region("Validation");
    const check = within(validation).getByTestId("check-cell_accounting");
    expect(within(check).getByText("Pass")).toBeInTheDocument();
    expect(within(validation).getByTestId("check-mixed_columns")).toHaveTextContent("2");
    expect(within(validation).getByTestId("dataset-sha256")).toHaveTextContent(
      (PROFILE as ProfileResponse).dataset.sha256,
    );

    const [sent] = profileCalls(api).map(([, init]) => JSON.parse(String(init?.body)));
    expect(sent).toEqual({
      source: { kind: "sample", sample_id: "messy_survey" },
      options: {
        delimiter: "comma",
        missing_markers: ["NA", "N/A", "NaN", "None", "null"],
        column_types: [],
      },
      save_experiment: false,
    });
  });

  it("uploads a file's exact bytes as base64 and never sends its name", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    const file = new File(["a,b\n1,2\n"], "secret-names.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/^CSV file/), file);
    await userEvent.click(screen.getByLabelText(/Save to the experiment log/));
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await screen.findByTestId("profile-rows");

    const [, init] = profileCalls(api)[0]!;
    const sent = JSON.parse(String(init?.body));
    expect(sent.source).toEqual({ kind: "upload", content_base64: btoa("a,b\n1,2\n") });
    expect(sent.save_experiment).toBe(true);
    expect(String(init?.body)).not.toContain("secret-names");
  });

  it("refuses a file over the limit without contacting the server", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    const big = new File([new Uint8Array(MAX_FILE_BYTES + 1)], "big.csv", { type: "text/csv" });
    await userEvent.upload(screen.getByLabelText(/^CSV file/), big);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("the limit is 2 MiB");
    expect(profileCalls(api)).toHaveLength(0);
  });

  it("asks for a file when none is chosen", async () => {
    mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Choose a CSV file first.");
  });

  it("shows the server's explanation of a malformed file", async () => {
    const detail =
      "Every row must have 3 fields, like the header. 1 row(s) do not: row 2 (line 3) has 2.";
    mockApi(() => json(422, { detail }));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    await userEvent.upload(
      screen.getByLabelText(/^CSV file/),
      new File(["a,b,c\n1,2,3\n4,5\n"], "x.csv"),
    );
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(detail);
  });

  it("marks results stale when settings change, and sends overrides by column position", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await screen.findByTestId("profile-rows");
    expect(screen.queryByText(/have changed since this profile/)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("income_gbp"), "numeric");
    expect(screen.getAllByText(/have changed since this profile/)).toHaveLength(2);
    // Back to the profiled settings: no longer stale.
    await userEvent.selectOptions(screen.getByLabelText("income_gbp"), "");
    expect(screen.queryByText(/have changed since this profile/)).not.toBeInTheDocument();

    await userEvent.selectOptions(screen.getByLabelText("income_gbp"), "numeric");
    const markers = screen.getByLabelText("Missing-value markers");
    await userEvent.clear(markers);
    await userEvent.type(markers, "NaN, n/a");
    await userEvent.click(screen.getByRole("button", { name: "Profile again" }));
    await vi.waitFor(() => expect(profileCalls(api)).toHaveLength(2));
    const sent = JSON.parse(String(profileCalls(api)[1]![1]?.body));
    expect(sent.options).toEqual({
      delimiter: "comma",
      missing_markers: ["NaN", "n/a"],
      column_types: [{ column: 3, type: "numeric" }],
    });
    expect(String(profileCalls(api)[1]![1]?.body)).not.toContain("income_gbp");
  });

  it("clears overrides when another dataset is chosen", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await screen.findByTestId("profile-rows");
    await userEvent.selectOptions(screen.getByLabelText("rating"), "numeric");
    await userEvent.selectOptions(
      await screen.findByLabelText("Sample dataset"),
      "lab_measurements",
    );
    expect(screen.queryByLabelText("rating")).not.toBeInTheDocument(); // old file's columns
    expect(screen.getAllByText(/have changed since this profile/)).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Profile again" }));
    await vi.waitFor(() => expect(profileCalls(api)).toHaveLength(2));
    const sent = JSON.parse(String(profileCalls(api)[1]![1]?.body));
    expect(sent.source).toEqual({ kind: "sample", sample_id: "lab_measurements" });
    expect(sent.options.column_types).toEqual([]);
  });

  it("clears overrides when the delimiter changes, because the columns may change", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    await screen.findByTestId("profile-rows");
    await userEvent.selectOptions(screen.getByLabelText("income_gbp"), "numeric");
    await userEvent.selectOptions(screen.getByLabelText("Delimiter"), "semicolon");
    // Column positions from the comma reading no longer apply: no override controls.
    expect(screen.queryByLabelText("income_gbp")).not.toBeInTheDocument();
    expect(screen.getAllByText(/have changed since this profile/)).toHaveLength(2);
    await userEvent.click(screen.getByRole("button", { name: "Profile again" }));
    await vi.waitFor(() => expect(profileCalls(api)).toHaveLength(2));
    const sent = JSON.parse(String(profileCalls(api)[1]![1]?.body));
    expect(sent.options.delimiter).toBe("semicolon");
    expect(sent.options.column_types).toEqual([]);
  });

  it("explains a file that can no longer be read, without contacting the server", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    const file = new File(["a\n1\n"], "gone.csv", { type: "text/csv" });
    // The file was moved or edited after it was chosen: reading it fails.
    Object.defineProperty(file, "arrayBuffer", {
      value: () => Promise.reject(new DOMException("changed", "NotReadableError")),
    });
    await userEvent.upload(screen.getByLabelText(/^CSV file/), file);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not read the file");
    expect(profileCalls(api)).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Profile dataset" })).toBeEnabled();
  });

  it("ignores a second click while the file is still being read", async () => {
    const api = mockApi(() => json(200, PROFILE));
    render(<QuantLab />);
    await userEvent.click(screen.getByLabelText("Upload a CSV file"));
    const file = new File(["a\n1\n"], "slow.csv", { type: "text/csv" });
    let finishReading: (b: ArrayBuffer) => void = () => {};
    Object.defineProperty(file, "arrayBuffer", {
      value: () => new Promise<ArrayBuffer>((resolve) => (finishReading = resolve)),
    });
    await userEvent.upload(screen.getByLabelText(/^CSV file/), file);
    await userEvent.click(screen.getByRole("button", { name: "Profile dataset" }));
    const button = screen.getByRole("button", { name: "Profiling…" });
    expect(button).toBeDisabled();
    await userEvent.click(button);
    finishReading(new TextEncoder().encode("a\n1\n").buffer as ArrayBuffer);
    await screen.findByTestId("profile-rows");
    expect(profileCalls(api)).toHaveLength(1);
  });
});
