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

  const rangeRow = page.getByRole("row", { name: /Range/ });
  const expectedRange = (10 ** 2 * Math.sin((60 * Math.PI) / 180)) / 9.80665; // 8.830885...
  await expect(rangeRow).toContainText(expectedRange.toPrecision(8));

  // Error is reported in scientific notation and is tiny.
  const maxError = await page.getByTestId("max-position-error").innerText();
  expect(Number.parseFloat(maxError)).toBeLessThan(1e-6);

  // Plotly rendered both charts.
  await expect(page.locator(".chart .main-svg").first()).toBeVisible();
  await expect(page.locator(".chart")).toHaveCount(2);

  await page.getByRole("link", { name: "Experiments" }).click();
  await expect(page.getByRole("heading", { name: "Experiment log" })).toBeVisible();
  await expect(page.getByRole("row").nth(1)).toContainText("physics.projectile");
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
