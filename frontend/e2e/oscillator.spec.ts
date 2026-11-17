import { expect, test, type Page } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

// Full stack for the harmonic oscillator (roadmap 2.3): browser -> Next.js -> FastAPI ->
// SciPy -> SQLite. Every run uses inputs no other test uses and is found in the log by its
// own id. Expected values are the textbook closed forms, computed here from the typed inputs
// (w0 = sqrt(k/m), gamma = b/2m, zeta = b/(2 sqrt(mk)), Q = sqrt(mk)/b, A = F0/(b w) at
// w = w0), never read back from the page.

const region = (page: Page, name: string) => page.getByRole("region", { name });
const results = (page: Page) => region(page, "Results");

/** The number in the value cell beside a Results label (units and text ignored). */
async function valueOf(page: Page, label: string): Promise<number> {
  const dd = results(page).getByText(label, { exact: true }).locator("xpath=following-sibling::dd");
  return Number.parseFloat((await dd.first().textContent())!);
}

/** The page shows at least 6 significant figures (checked loosely): 1e-5 relative covers the
 *  rounding of a 6-figure display (at most 5e-6) with margin. */
function expectClose(actual: number, expected: number) {
  expect(Math.abs(actual - expected)).toBeLessThanOrEqual(1e-5 * Math.abs(expected));
}

async function setInputs(page: Page, inputs: Record<string, string>) {
  for (const [label, value] of Object.entries(inputs)) {
    await page.getByLabel(new RegExp(`^${label}`)).fill(value);
  }
}

/** Reopen the run from the experiment log and check the inputs come back. */
async function logAndReopen(page: Page, runId: string, inputs: Record<string, string>) {
  await page.getByRole("link", { name: "Experiments" }).click();
  await page.getByRole("button", { name: "Physics" }).click();
  const row = logRow(page, runId);
  await expect(row).toContainText("physics.oscillator");
  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/physics/oscillator\\?run=${runId}`));
  await expect(page.getByText(/Loaded the inputs of run/)).toBeVisible();
  for (const [label, value] of Object.entries(inputs)) {
    await expect(page.getByLabel(new RegExp(`^${label}`))).toHaveValue(value);
  }
}

test("the page is reached from the nav link and from the home-page card", async ({ page }) => {
  await page.goto("/");
  await page
    .getByRole("navigation", { name: "Main" })
    .getByRole("link", { name: "Oscillators" })
    .click();
  await expect(page).toHaveURL(/\/physics\/oscillator$/);
  await expect(page.getByRole("heading", { level: 1, name: /Harmonic oscillator/ })).toBeVisible();

  await page.goto("/");
  await page.getByRole("link", { name: "Open Oscillators" }).click();
  await expect(page).toHaveURL(/\/physics\/oscillator$/);
  for (const name of ["Simple", "Damped", "Driven"]) {
    await expect(page.getByRole("button", { name })).toBeVisible();
  }
});

test("Simple preset: undamped SHM has w0 = sqrt(k/m), no Q, no steady state", async ({ page }) => {
  await page.goto("/physics/oscillator");
  await page.getByRole("button", { name: "Simple" }).click();
  const inputs = { Mass: "1.3", "Spring constant": "31.7", Duration: "11.5" };
  await setInputs(page, inputs);
  await page.getByRole("button", { name: "Run simulation" }).click();
  const runId = await shownRunId(page);

  expectClose(await valueOf(page, "Natural angular frequency ω₀ (formula)"), Math.sqrt(31.7 / 1.3));
  const w0 = Math.sqrt(31.7 / 1.3);
  expectClose(await valueOf(page, "Damped period T_d (formula)"), (2 * Math.PI) / w0);
  await expect(
    results(page).getByText("Regime (exact)").locator("xpath=following-sibling::dd"),
  ).toContainText(/undamped/i);
  // D12's nulls: shown as absent, never as 0.
  for (const label of ["Quality factor Q (formula)", "Steady-state amplitude A (formula)"]) {
    const dd = results(page)
      .getByText(label, { exact: true })
      .locator("xpath=following-sibling::dd");
    await expect(dd).toHaveText(/^none/);
  }
  await expect(region(page, "Validation").getByTestId("check-energy_balance")).toContainText(
    "Pass",
  );
  const vis = region(page, "Visualisation");
  await expect(vis.locator(".chart .main-svg").first()).toBeVisible();
  await expect(vis.locator(".chart")).toHaveCount(2); // no resonance curve without a drive

  await logAndReopen(page, runId, inputs);
});

test("Damped preset: gamma, zeta, Q and the damped period from their formulas", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  await page.getByRole("button", { name: "Damped" }).click();
  const inputs = { Mass: "1.7", "Spring constant": "26.3", "Damping coefficient": "0.41" };
  await setInputs(page, inputs);
  await page.getByRole("button", { name: "Run simulation" }).click();
  const runId = await shownRunId(page);

  const [m, k, b] = [1.7, 26.3, 0.41];
  const w0 = Math.sqrt(k / m);
  const gamma = b / (2 * m);
  expectClose(await valueOf(page, "Damping rate γ (formula)"), gamma);
  expectClose(await valueOf(page, "Damping ratio ζ (formula)"), b / (2 * Math.sqrt(m * k)));
  expectClose(await valueOf(page, "Quality factor Q (formula)"), Math.sqrt(m * k) / b);
  expectClose(
    await valueOf(page, "Damped period T_d (formula)"),
    (2 * Math.PI) / Math.sqrt(w0 * w0 - gamma * gamma),
  );
  await expect(
    results(page).getByText("Regime (exact)").locator("xpath=following-sibling::dd"),
  ).toContainText(/underdamped/i);
  const validation = region(page, "Validation");
  await expect(validation.getByTestId("check-energy_balance")).toContainText("Pass");
  await expect(
    validation.getByText("Saved to experiment log").locator("xpath=following-sibling::dd[1]"),
  ).toHaveText("Yes");
  await expect(region(page, "Visualisation").locator(".chart")).toHaveCount(2);

  await logAndReopen(page, runId, inputs);
});

test("Driven preset at resonance: A = F0/(b w0), phase lag pi/2, and the resonance chart", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  await page.getByRole("button", { name: "Driven" }).click();
  const [m, k, b, F0] = [0.9, 22.1, 0.37, 1.9];
  const w0 = Math.sqrt(k / m);
  // The drive frequency is typed to 10 significant figures: w = w0 to 1e-10 relative.
  const inputs = {
    Mass: String(m),
    "Spring constant": String(k),
    "Damping coefficient": String(b),
    "Drive amplitude": String(F0),
    "Drive angular frequency": String(Number(w0.toPrecision(10))),
  };
  await setInputs(page, inputs);
  await page.getByRole("button", { name: "Run simulation" }).click();
  const runId = await shownRunId(page);

  // A = (F0/m)/(2 gamma w) = F0/(b w) at w = w0 (exact formula); delta = pi/2 there.
  expectClose(await valueOf(page, "Steady-state amplitude A (formula)"), F0 / (b * w0));
  expectClose(await valueOf(page, "Phase lag δ (formula)"), Math.PI / 2);
  await expect(region(page, "Validation").getByTestId("check-energy_balance")).toContainText(
    "Pass",
  );
  const vis = region(page, "Visualisation");
  await expect(vis.locator(".chart")).toHaveCount(3); // displacement, energy, resonance
  await expect(
    vis
      .getByRole("img", {
        name: "Resonance: steady-state amplitude and phase against drive frequency",
      })
      .locator(".main-svg")
      .first(),
  ).toBeVisible();

  await logAndReopen(page, runId, inputs);
});

test("pin a reference run and see its curve on the displacement and energy charts", async ({
  page,
}) => {
  await page.goto("/physics/oscillator");
  await page.getByRole("button", { name: "Damped" }).click();
  await setInputs(page, { Mass: "1.9", "Spring constant": "23.9", "Damping coefficient": "0.33" });
  await page.getByRole("button", { name: "Run simulation" }).click();
  const referenceId = await shownRunId(page);

  const reference = region(page, "Reference run");
  await reference.getByRole("button", { name: "Pin as reference run" }).click();
  await expect(page).toHaveURL(new RegExp(`[?&]ref=${referenceId}`));

  await setInputs(page, { "Damping coefficient": "0.66" });
  await page.getByRole("button", { name: "Run simulation" }).click();
  await expect
    .poll(async () => shownRunId(page), { message: "a second run is shown" })
    .not.toBe(referenceId);

  for (const title of ["Displacement against time", "Energy against time"]) {
    const chart = page.getByRole("img", { name: title });
    await expect(chart.locator(".legendtext", { hasText: "reference run" }).first()).toBeVisible();
    const faded = await chart.evaluate((el) =>
      (
        el as unknown as { data: { name?: string; opacity?: number; line?: { dash?: string } }[] }
      ).data
        .filter((t) => t.name === "reference run")
        .map((t) => ({ opacity: t.opacity, dash: t.line?.dash })),
    );
    expect(faded.length).toBeGreaterThanOrEqual(1);
    for (const t of faded) {
      expect(t.opacity).toBeLessThan(1);
      expect(t.dash).toBe("dash");
    }
  }
  // Only the changed input differs.
  const inputsTable = reference.getByRole("table", { name: /Inputs that differ/ });
  await expect(inputsTable.locator("tbody tr")).toHaveCount(1);
  await expect(inputsTable.locator("tbody tr th")).toHaveText("parameters.damping_coefficient");
  await expect(inputsTable.locator("tbody tr td")).toHaveText(["0.33", "0.66"]);
});
