import { expect, test } from "@playwright/test";

// Full stack for the Economy Lab: browser -> Next.js -> FastAPI -> NumPy -> SQLite.
test("run the Solow model and find it in the experiment log", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Open Economy Lab" }).click();
  await expect(page.getByRole("heading", { name: "Solow growth model" })).toBeVisible();
  for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }

  // Defaults: alpha = 0.3, s0 = 0.2, delta = 0.05, n = 0.01, g = 0.02. Move to s1 = alpha.
  await page.getByLabel(/^New savings rate/).fill("0.3");
  await page.getByLabel(/^Policy year/).fill("10");
  await page.getByRole("button", { name: "Run model" }).click();

  // k* = (s / lambda)^(1/(1 - alpha)) with lambda = n + g + n g + delta, computed here
  // independently of the backend.
  const lambda = 0.01 + 0.02 + 0.01 * 0.02 + 0.05;
  const kStar = (s: number) => (s / lambda) ** (1 / 0.7);
  await expect(page.getByTestId("steady-state-baseline")).toHaveText(
    String(Number(kStar(0.2).toPrecision(6))),
  );
  await expect(page.getByTestId("steady-state-scenario")).toHaveText(
    String(Number(kStar(0.3).toPrecision(6))),
  );
  await expect(page.getByTestId("golden-rule-sentence")).toContainText(
    "equal to the golden-rule rate",
  );
  await expect(page.getByTestId("check-identical_before_policy")).toContainText("Pass");

  await expect(page.locator(".chart .main-svg").first()).toBeVisible();
  await expect(page.locator(".chart")).toHaveCount(3);

  await page.getByRole("link", { name: "Experiments" }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: /economy\.solow v1/ })
    .first();
  await expect(row).toContainText(
    `k* ${Number(kStar(0.2).toPrecision(4))} → ${Number(kStar(0.3).toPrecision(4))}`,
  );
});
