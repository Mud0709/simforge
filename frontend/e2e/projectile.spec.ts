import { expect, test } from "@playwright/test";

// Full stack: browser -> Next.js -> FastAPI -> SciPy -> SQLite, and back.
test("run a projectile simulation and find it in the experiment log", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Open Physics Lab" }).click();
  await expect(
    page.getByRole("heading", { name: "Projectile motion with linear drag" }),
  ).toBeVisible();

  // Vacuum case so the result can be checked against R = v^2 sin(2θ) / g.
  await page.getByLabel(/^Initial speed/).fill("10");
  await page.getByLabel(/^Launch angle/).fill("30");
  await page.getByLabel(/^Drag coefficient/).fill("0");
  await page.getByRole("button", { name: "Run simulation" }).click();

  // The shared workspace: the comparison with the exact solution lives under Validation.
  for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }
  const rangeRow = page
    .getByRole("region", { name: "Validation" })
    .getByRole("row", { name: /Range/ });
  const expectedRange = (10 ** 2 * Math.sin((60 * Math.PI) / 180)) / 9.80665; // 8.83100...
  await expect(rangeRow).toContainText(expectedRange.toPrecision(8));

  // Error is reported in scientific notation and is tiny.
  const maxError = await page.getByTestId("max-position-error").innerText();
  expect(Number.parseFloat(maxError)).toBeLessThan(1e-6);

  // Plotly rendered both charts.
  await expect(page.locator(".chart .main-svg").first()).toBeVisible();
  await expect(page.locator(".chart")).toHaveCount(2);

  await page.getByRole("link", { name: "Experiments" }).click();
  await expect(page.getByRole("heading", { name: "Experiment log" })).toBeVisible();
  // Other E2E tests share this database and may run in parallel, so match this run's row
  // by its model and solver rather than assuming it is the newest.
  const row = page
    .getByRole("row")
    .filter({ hasText: /physics\.projectile v1/ })
    .first();
  await expect(row).toContainText("DOP853");
  await expect(row).toContainText(`range ${Number(expectedRange.toPrecision(6))} m`);
});

test("invalid input is rejected without calling the API", async ({ page }) => {
  let apiCalls = 0;
  page.on("request", (r) => {
    if (r.url().includes("/api/v1/physics")) apiCalls++;
  });
  await page.goto("/physics/projectile");
  await page.getByLabel(/^Mass/).fill("NaN");
  await page.getByRole("button", { name: "Run simulation" }).click();
  await expect(page.getByText("Must be a finite number")).toBeVisible();
  expect(apiCalls).toBe(0);
});

test("angle sweep finds 45 degrees in a vacuum from the ground", async ({ page }) => {
  await page.goto("/physics/projectile");
  await page.getByLabel(/^Initial speed/).fill("10");
  await page.getByLabel(/^Drag coefficient/).fill("0");
  await page.getByRole("button", { name: "Run simulation" }).click();

  await page.getByRole("button", { name: "Sweep launch angle" }).click();
  await expect(page.getByTestId("best-angle")).toHaveText("45.00°");
  // R = v^2 / g = 100 / 9.80665 = 10.1972 m (6 significant figures)
  await expect(page.getByTestId("best-range")).toHaveText(
    `${Number((100 / 9.80665).toPrecision(6))} m`,
  );
  const chart = page.getByRole("img", { name: "Range against launch angle" });
  await expect(chart.locator(".main-svg").first()).toBeVisible();
  await expect(chart).toContainText("Launch angle (°)");
});
