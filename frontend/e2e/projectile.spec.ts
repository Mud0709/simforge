import { expect, test } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

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

  // The shared workspace: each part of the result is checked inside its own region, after
  // the run (the regions exist, with placeholders, before it).
  const region = (name: string) => page.getByRole("region", { name });
  const validation = region("Validation");
  const rangeRow = validation.getByRole("row", { name: /Range/ });
  const expectedRange = (10 ** 2 * Math.sin((60 * Math.PI) / 180)) / 9.80665; // 8.83100...
  await expect(rangeRow).toContainText(expectedRange.toPrecision(8));

  // Error is reported in scientific notation and is tiny.
  const maxError = await validation.getByTestId("max-position-error").innerText();
  expect(Number.parseFloat(maxError)).toBeLessThan(1e-6);
  await expect(region("Results").getByText("Range (analytical)")).toBeVisible();
  await expect(region("Assumptions").locator("li").first()).toBeVisible();

  // Plotly rendered both charts, in Visualisation and nowhere else.
  const vis = region("Visualisation");
  await expect(vis.locator(".chart .main-svg").first()).toBeVisible();
  await expect(vis.locator(".chart")).toHaveCount(2);
  await expect(page.locator(".chart")).toHaveCount(2);

  const runId = await shownRunId(page);
  await page.getByRole("link", { name: "Experiments" }).click();
  const row = logRow(page, runId);
  await expect(row).toContainText(`range ${Number(expectedRange.toPrecision(6))} m`);
});

test("the run button stays reachable on a short window after a run", async ({ page }) => {
  // A 768 px-high laptop window: the form is taller than the screen, and the panel is sticky.
  await page.setViewportSize({ width: 1280, height: 768 });
  await page.goto("/physics/projectile");
  await page.getByRole("button", { name: "Run simulation" }).click();
  await expect(page.getByTestId("max-position-error")).toBeVisible();
  // Scroll part-way down, where the panel is stuck to the top (near the very bottom of the
  // page it scrolls away with its container, and would look fine either way).
  await page.evaluate(() => window.scrollTo(0, 400));
  const panel = page.getByRole("region", { name: "Parameters" });
  await expect.poll(async () => (await panel.boundingBox())!.y).toBeCloseTo(16, 0);

  // The stuck panel fits inside the window, so nothing in it is cut off below the screen...
  const box = (await panel.boundingBox())!;
  expect(box.y + box.height).toBeLessThanOrEqual(768);
  // ...and the button is reached by scrolling inside the panel, not by moving the page.
  const button = page.getByRole("button", { name: "Run simulation" });
  await button.scrollIntoViewIfNeeded();
  await expect(button).toBeInViewport();
  expect(await page.evaluate(() => window.scrollY)).toBe(400);
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
