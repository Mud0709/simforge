import { expect, test } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

// Full stack for quadratic drag (roadmap 2.1): browser -> Next.js -> FastAPI -> SciPy ->
// SQLite. Inputs no other test uses, and the run is found in the log by its own id.
test("run quadratic drag, find the run in the experiment log and reopen it", async ({ page }) => {
  await page.goto("/physics/projectile");
  await page
    .locator("header.page-header")
    .getByRole("link", { name: /quadratic drag/i })
    .click();
  await expect(
    page.getByRole("heading", { level: 1, name: "Projectile motion with quadratic drag" }),
  ).toBeVisible();

  await page.getByLabel(/^Initial speed/).fill("17.5");
  await page.getByLabel(/^Launch angle/).fill("38");
  await page.getByLabel(/^Drag constant c/).fill("0.0137");
  await page.getByRole("button", { name: "Run simulation" }).click();
  const runId = await shownRunId(page);

  const region = (name: string) => page.getByRole("region", { name });
  await expect(region("Results").getByText("Range (numerical)")).toBeVisible();
  // v_t = sqrt(m g / c) = sqrt(1 x 9.80665 / 0.0137) = 26.7547... m/s (hand-computed).
  const vT = Math.sqrt(9.80665 / 0.0137);
  await expect(
    region("Results")
      .getByText("Terminal speed v_t (exact)")
      .locator("xpath=following-sibling::dd"),
  ).toHaveText(`${Number(vT.toPrecision(8))} m/s`);
  const validation = region("Validation");
  await expect(validation.getByTestId("check-energy_balance")).toContainText("Pass");
  await expect(validation.getByTestId("check-hodograph_invariant")).toContainText("Pass");
  await expect(
    validation.getByText("Saved to experiment log").locator("xpath=following-sibling::dd[1]"),
  ).toHaveText("Yes");
  // Plotly drew the three charts, in Visualisation.
  const vis = region("Visualisation");
  await expect(vis.locator(".chart .main-svg").first()).toBeVisible();
  await expect(vis.locator(".chart")).toHaveCount(3);

  await page.getByRole("link", { name: "Experiments" }).click();
  await page.getByRole("button", { name: "Physics" }).click();
  const row = logRow(page, runId);
  await expect(row).toContainText("physics.projectile.quadratic_drag");
  await expect(row).toContainText(`v_t ${Number(vT.toPrecision(6))} m/s`);
  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/physics/projectile/quadratic-drag\\?run=${runId}`));
  await expect(page.getByText(/Loaded the inputs of run/)).toBeVisible();
  await expect(page.getByLabel(/^Initial speed/)).toHaveValue("17.5");
  await expect(page.getByLabel(/^Launch angle/)).toHaveValue("38");
  await expect(page.getByLabel(/^Drag constant c/)).toHaveValue("0.0137");
});

test("a vertical launch is checked against the exact vertical flight", async ({ page }) => {
  await page.goto("/physics/projectile/quadratic-drag");
  await page.getByLabel(/^Initial speed/).fill("13.5");
  await page.getByLabel(/^Launch angle/).fill("90");
  await page.getByLabel(/^Drag constant c/).fill("0.0211");
  await page.getByRole("button", { name: "Run simulation" }).click();
  const validation = page.getByRole("region", { name: "Validation" });
  await expect(validation.getByText("Exact vertical flight vs numerical")).toBeVisible();
  await expect(validation.getByTestId("check-vertical_flight_time")).toContainText("Pass");
  // The invariant divides by vx, which is 0 here: shown as not available, never as a number.
  await expect(validation.getByTestId("check-hodograph_invariant")).toContainText("not available");
});

test("sweep the launch angle with quadratic drag, pin it, find it in the log and reopen it", async ({
  page,
}) => {
  await page.goto("/physics/projectile/quadratic-drag");
  await page.getByLabel(/^Initial speed/).fill("16.3");
  await page.getByLabel(/^Drag constant c/).fill("0.0123");
  await page.getByRole("button", { name: "Run simulation" }).click();
  await shownRunId(page);

  const results = page.getByRole("region", { name: "Results" });
  // Few angles, so the sweep is quick: 11 runs on the grid plus the refinement.
  await results.getByLabel(/^Number of angles/).fill("11");
  await results.getByRole("button", { name: "Sweep launch angle" }).click();

  // Drag lowers the best angle below the vacuum's 45° (from the ground); the vacuum optimum
  // from the ground is exactly 45° (formula).
  const best = page.getByTestId("best-angle");
  await expect(best).toHaveText(/^\d+\.\d\d° ± .+° \(estimate\)$/);
  expect(Number.parseFloat((await best.textContent())!)).toBeLessThan(45);
  await expect(page.getByTestId("vacuum-angle")).toContainText("45.00°");
  await expect(page.getByTestId("peak-count")).toHaveText("1");
  const chart = page.getByRole("img", { name: "Range against launch angle" });
  await expect(chart.locator(".main-svg").first()).toBeVisible();

  const checks = page
    .getByRole("region", { name: "Validation" })
    .getByRole("region", { name: "Angle sweep: checks over every run" });
  await expect(checks.getByTestId("check-energy_balance")).toContainText("Pass");
  await expect(checks.getByText(/largest value \/ threshold is at/).first()).toBeVisible();
  await expect(
    checks.getByText("Saved to experiment log").locator("xpath=following-sibling::dd[1]"),
  ).toHaveText("Yes");
  const sweepId = (await checks.locator("dl.meta code").first().textContent())!;

  await page.getByRole("button", { name: "Pin sweep as reference run" }).click();
  await expect(page.getByText("This sweep is the reference run.")).toBeVisible();

  await page.getByRole("link", { name: "Experiments" }).click();
  await page.getByRole("button", { name: "Physics" }).click();
  const row = logRow(page, sweepId);
  await expect(row).toContainText("physics.projectile.quadratic_angle_sweep");
  await expect(row).toContainText("best angle");
  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/physics/projectile/quadratic-drag\\?run=${sweepId}`));
  await expect(page.getByText(/Run the simulation, then sweep the launch angle/)).toBeVisible();
  await expect(page.getByLabel(/^Initial speed/)).toHaveValue("16.3");
  await expect(page.getByLabel(/^Drag constant c/)).toHaveValue("0.0123");
  // The sweep's own setting comes back too, under the next simulation's results.
  await page.getByRole("button", { name: "Run simulation" }).click();
  await expect(
    page.getByRole("region", { name: "Results" }).getByLabel(/^Number of angles/),
  ).toHaveValue("11");
});
