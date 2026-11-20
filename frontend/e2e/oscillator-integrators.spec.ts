import { expect, test, type Page } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

// Full stack for roadmap 2.4's oscillator integrator workbench (builder: see the contract in
// src/components/OscillatorIntegratorLab.test.tsx). Orders are compared with theory (Euler and
// symplectic Euler 1, velocity Verlet 2, RK4 4): +-0.15 covers the pre-asymptotic bias of a
// 3+ point fit over h = T/N with theta = w h <= 0.2 (the measured spread is the backend
// slice's SCIENTIFIC_VALIDATION figure); the run is found in the log by its own id.
const region = (page: Page, name: string) => page.getByRole("region", { name });

test("the page is reached from the oscillator page and runs its default", async ({ page }) => {
  await page.goto("/physics/oscillator");
  await page.getByRole("link", { name: /Compare integrators on the oscillator/ }).click();
  await expect(page).toHaveURL(/\/physics\/oscillator\/integrators$/);

  await page.getByRole("button", { name: "Run study" }).click();
  const results = region(page, "Results");
  for (const [method, order] of [
    ["euler", 1],
    ["symplectic_euler", 1],
    ["velocity_verlet", 2],
    ["rk4", 4],
  ] as const) {
    const fitted = await results.getByTestId(`order-${method}`).locator("td").nth(1).innerText();
    expect(Math.abs(Number.parseFloat(fitted) - order)).toBeLessThan(0.15);
  }

  // Both charts are drawn, with labelled axes.
  const vis = region(page, "Visualisation");
  const conv = vis.getByRole("img", {
    name: "Convergence: maximum scaled error against time step",
  });
  await expect(conv.locator(".main-svg").first()).toBeVisible();
  await expect(conv).toContainText("Time step h (s)");
  const drift = vis.getByRole("img", {
    name: "Energy drift: relative energy envelope against time",
  });
  await expect(drift.locator(".main-svg").first()).toBeVisible();
  await expect(drift).toContainText("Time (s)");

  // The checks of the default run all pass (information rows have no verdict).
  const validation = region(page, "Validation");
  await expect(validation.locator(".check-status.fail")).toHaveCount(0);
  await expect(validation.locator(".check-status.pass").first()).toBeVisible();
});

test("a run is saved, listed and reopened with its inputs", async ({ page }) => {
  await page.goto("/physics/oscillator/integrators");
  await page.getByLabel(/^Mass/).fill("1.3");
  await page.getByLabel(/^Spring constant/).fill("31.7");
  await page.getByLabel(/^Periods/).fill("37");
  await page.getByRole("button", { name: "Run study" }).click();
  const runId = await shownRunId(page);

  await page.getByRole("link", { name: "Experiments" }).click();
  await page.getByRole("button", { name: "Physics" }).click();
  const row = logRow(page, runId);
  await expect(row).toContainText("physics.oscillator.integrators");
  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/physics/oscillator/integrators\\?run=${runId}`));
  await expect(page.getByText(/Loaded the inputs of run/)).toBeVisible();
  await expect(page.getByLabel(/^Mass/)).toHaveValue("1.3");
  await expect(page.getByLabel(/^Spring constant/)).toHaveValue("31.7");
  await expect(page.getByLabel(/^Periods/)).toHaveValue("37");
});

test("a server-side refusal is explained to the user", async ({ page }) => {
  await page.goto("/physics/oscillator/integrators");
  await page.getByLabel(/^Periods/).fill("5000");
  await page.getByRole("button", { name: "Run study" }).click();
  await expect(page.locator("p.api-error[role=alert]")).toBeVisible();
});
