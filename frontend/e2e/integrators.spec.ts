import { expect, test } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

// Full stack: browser -> Next.js -> FastAPI -> from-scratch integrators -> SQLite.
test("integrator study shows fitted orders near theory and log-log plots", async ({ page }) => {
  await page.goto("/physics/projectile");
  await page.getByRole("link", { name: /Compare fixed-step integrators/ }).click();
  await expect(
    page.getByRole("heading", { name: "How fast do integrators converge?" }),
  ).toBeVisible();

  await page.getByRole("button", { name: "Run study" }).click();
  // Each part is checked inside its own region (the regions exist before the run).
  const region = (name: string) => page.getByRole("region", { name });
  const results = region("Results");
  const vis = region("Visualisation");

  for (const [method, order] of [
    ["euler", 1],
    ["rk4", 4],
    ["verlet", 2],
  ] as const) {
    const fitted = await results.getByTestId(`order-${method}`).locator("td").nth(1).innerText();
    expect(Math.abs(Number.parseFloat(fitted) - order)).toBeLessThan(0.1);
  }

  // Both convergence plots rendered with logarithmic axes and labelled units.
  const plot = vis.getByRole("img", { name: /maximum position error against time step/ });
  await expect(plot.locator(".main-svg").first()).toBeVisible();
  await expect(plot).toContainText("Time step h (s)");
  await expect(plot).toContainText("Max position error over grid nodes (m)");
  await expect(vis.locator(".chart")).toHaveCount(3);
  await expect(page.locator(".chart")).toHaveCount(3);
  // One heading per method (outside its <summary>, so every screen reader lists it).
  await expect(region("Validation").getByRole("heading", { name: /^All runs:/ })).toHaveCount(3);

  const runId = await shownRunId(page);
  await page.getByRole("link", { name: "Experiments" }).click();
  const row = logRow(page, runId);
  await expect(row).toContainText(/rk4 p≈(3\.9|4\.0|4\.1)/);
});

test("a server-side refusal is explained to the user", async ({ page }) => {
  await page.goto("/physics/projectile/integrators");
  await page.getByLabel(/^Time steps/).fill("0.1, 0.000001");
  await page.getByRole("button", { name: "Run study" }).click();
  await expect(page.locator("p.api-error[role=alert]")).toContainText("limit is 50000 per run");
});
