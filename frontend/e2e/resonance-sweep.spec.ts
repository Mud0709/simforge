import { expect, test, type Page } from "@playwright/test";

import { logRow } from "./helpers";

// Full stack for the simulated resonance curve (roadmap 2.5, slice 5): browser -> Next.js ->
// FastAPI -> SciPy -> SQLite, on /physics/oscillator. Every run uses inputs no other test uses
// and is found in the log by its own id. Expected values are the textbook closed forms,
// computed here from the typed inputs, never read back from the page:
//   w0 = sqrt(k/m), gamma = b/2m, w_r = sqrt(w0^2 - 2 gamma^2) (when w0^2 > 2 gamma^2),
//   A_max = (F0/m) / (2 gamma sqrt(w0^2 - gamma^2)).
// The panel's own labels are "Sweep ..." / "Lowest ..." / "Highest ..." so that they cannot
// match the simulation form's (^Mass, ^Spring constant, ...) on the same page.

const panel = (page: Page) => page.getByRole("region", { name: "Simulated resonance curve" });

async function setInputs(page: Page, inputs: Record<string, string>) {
  for (const [label, value] of Object.entries(inputs)) {
    await page.getByLabel(new RegExp(`^${label}`)).fill(value);
  }
}

/** The number at the start of a test id's text (units and words ignored). */
async function numberOf(page: Page, testId: string): Promise<number> {
  return Number.parseFloat((await page.getByTestId(testId).textContent())!);
}

/** The page shows at least 6 significant figures: 1e-5 relative covers the rounding of a
 *  6-figure display (at most 5e-6) with margin. */
function expectClose(actual: number, expected: number, rel = 1e-5) {
  expect(Math.abs(actual - expected)).toBeLessThanOrEqual(rel * Math.abs(expected));
}

test("sweep the drive frequency, compare with the formulas, find the run in the log and reopen it", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  const m = 1.3;
  const k = 31.7;
  const b = 0.9;
  const f0 = 1.7;
  await setInputs(page, {
    "Sweep mass": String(m),
    "Sweep spring constant": String(k),
    "Sweep damping coefficient": String(b),
    "Sweep drive amplitude": String(f0),
    "Lowest drive frequency": "3",
    "Highest drive frequency": "7",
    "Number of frequencies": "15",
  });
  await panel(page).getByRole("button", { name: "Sweep drive frequency" }).click();

  // Plotly drew the chart: the sweep is on screen once the numbers are.
  await expect(page.getByTestId("peak-frequency")).toBeVisible({ timeout: 30_000 });
  const chart = panel(page).getByRole("img", {
    name: "Simulated resonance curve: amplitude against drive frequency",
  });
  await expect(chart.locator(".main-svg").first()).toBeVisible();

  const w0sq = k / m;
  const gamma = b / (2 * m);
  const wr = Math.sqrt(w0sq - 2 * gamma * gamma);
  const aMax = f0 / m / (2 * gamma * Math.sqrt(w0sq - gamma * gamma));
  // The exact numbers are formulas: equal to 6 displayed figures.
  expectClose(await numberOf(page, "exact-peak-frequency"), wr);
  expectClose(await numberOf(page, "exact-peak-amplitude"), aMax);
  // The refined peak is numerical. The grid step is (7 - 3)/14 = 0.286 rad/s, so the grid alone
  // could miss w_r by up to 0.143 rad/s; a refined peak within 1e-3 rad/s (about a hundredth of
  // that, a 0.02% error in w_r) shows the refinement worked. Its amplitude is within 1e-4
  // relative of A_max: the settle tolerance is 1e-6 of A and the solver tolerance is far below.
  const peak = await numberOf(page, "peak-frequency");
  expect(Math.abs(peak - wr)).toBeLessThan(1e-3);
  expectClose(await numberOf(page, "peak-amplitude"), aMax, 1e-4);
  // The uncertainty is an estimate, and labelled as one.
  await expect(page.getByTestId("peak-frequency")).toHaveText(/ ± .+ rad\/s \(estimate\)$/);

  // C1 is proved given the measured trajectory error: it passes on a healthy run.
  await expect(page.getByTestId("check-lock_in_amplitude")).toContainText("Pass");
  await expect(page.getByTestId("check-extraction_amplitude")).toContainText("Pass");
  await expect(
    panel(page).getByText("Saved to experiment log").locator("xpath=following-sibling::dd[1]"),
  ).toHaveText("Yes");
  const sweepId = (await panel(page).locator("dl.meta code").first().textContent())!;

  await page.getByRole("link", { name: "Experiments" }).click();
  await page.getByRole("button", { name: "Physics" }).click();
  const row = logRow(page, sweepId);
  await expect(row).toContainText("physics.oscillator.resonance_sweep");
  await expect(row).toContainText(/peak .+ rad\/s/);
  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/physics/oscillator\\?run=${sweepId}`));
  await expect(page.getByText(/Loaded the inputs of run/)).toBeVisible();
  const reopened = panel(page);
  await expect(reopened.getByLabel(/^Sweep mass/)).toHaveValue("1.3");
  await expect(reopened.getByLabel(/^Sweep spring constant/)).toHaveValue("31.7");
  await expect(reopened.getByLabel(/^Sweep damping coefficient/)).toHaveValue("0.9");
  await expect(reopened.getByLabel(/^Sweep drive amplitude/)).toHaveValue("1.7");
  await expect(reopened.getByLabel(/^Lowest drive frequency/)).toHaveValue("3");
  await expect(reopened.getByLabel(/^Highest drive frequency/)).toHaveValue("7");
  await expect(reopened.getByLabel(/^Number of frequencies/)).toHaveValue("15");
  // The simulation form beside it is untouched.
  await expect(page.getByLabel(/^Mass/)).toHaveValue("1");
});

test("zeta above 1/sqrt 2 has no exact peak: w_r and A_max are absent and the best point is the lowest frequency", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  // m = 1, k = 25.3, b = 7.7: zeta = b / (2 sqrt(mk)) = 7.7 / 10.06 = 0.765 > 0.7071, and
  // b < 2 sqrt(mk) = 10.06, so it is still underdamped (the server accepts it).
  await setInputs(page, {
    "Sweep spring constant": "25.3",
    "Sweep damping coefficient": "7.7",
    "Lowest drive frequency": "1",
    "Highest drive frequency": "12",
    "Number of frequencies": "9",
  });
  await panel(page).getByRole("button", { name: "Sweep drive frequency" }).click();
  await expect(page.getByTestId("peak-frequency")).toBeVisible({ timeout: 30_000 });
  // A(w) = f / sqrt(D(w)), D = (w0^2 - w^2)^2 + (2 gamma w)^2, and D'(w) = 4w (w^2 - w0^2 + 2
  // gamma^2) > 0 for every w > 0 when w0^2 < 2 gamma^2 (zeta > 1/sqrt 2), so A decreases and
  // its maximum over [1, 12] is at w = 1, the lowest frequency: an edge, where no uncertainty
  // can be estimated.
  expectClose(await numberOf(page, "peak-frequency"), 1);
  await expect(page.getByTestId("peak-frequency")).not.toContainText("±");
  await expect(page.getByTestId("exact-peak-frequency")).toHaveText(/^none/);
  await expect(page.getByTestId("exact-peak-amplitude")).toHaveText(/^none/);
  // The curve and the checks are still there.
  await expect(
    panel(page)
      .getByRole("img", { name: "Simulated resonance curve: amplitude against drive frequency" })
      .locator(".main-svg")
      .first(),
  ).toBeVisible();
  await expect(page.getByTestId("check-lock_in_amplitude")).toContainText("Pass");
});

test("the server's reason is shown when the range is empty, and no result appears", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  // The combined rule omega_min < omega_max is checked by the server, not by the form.
  await setInputs(page, { "Lowest drive frequency": "9", "Highest drive frequency": "4" });
  await panel(page).getByRole("button", { name: "Sweep drive frequency" }).click();
  await expect(panel(page).getByRole("alert")).toContainText("must be below omega_max");
  await expect(page.getByTestId("peak-frequency")).toHaveCount(0);
});
