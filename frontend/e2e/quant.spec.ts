import { createHash } from "node:crypto";

import { expect, test } from "@playwright/test";

// Full stack for the Quant Lab: browser -> Next.js -> FastAPI -> parser/profile -> SQLite.
const CSV = [
  "station,temp_c,reading_date",
  "Oslo,-3.5,2026-01-05",
  "Lima,19,2026-01-05",
  "Oslo,-3.5,2026-01-05",
  "Cairo,NA,2026-01-06",
  "Lima,21.25,",
  "",
].join("\n");

test("upload a CSV, read its profile, override a type and find it in the log", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "Open Quant Research Lab" }).click();
  await expect(page.getByRole("heading", { name: "Dataset profile" })).toBeVisible();
  for (const name of ["Parameters", "Visualisation", "Results", "Assumptions", "Validation"]) {
    await expect(page.getByRole("region", { name })).toBeVisible();
  }

  await page.getByLabel("Upload a CSV file").check();
  await page.getByLabel(/^CSV file/).setInputFiles({
    name: "weather.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(CSV),
  });
  await page.getByLabel(/Save to the experiment log/).check();
  await page.getByRole("button", { name: "Profile dataset" }).click();

  const results = page.getByRole("region", { name: "Results" });
  await expect(results.getByTestId("profile-rows")).toHaveText("5");
  await expect(results.getByTestId("profile-columns")).toHaveText("3");
  // Missing: 'NA' in temp_c and the empty date: 2 of 15 cells.
  await expect(results.getByTestId("profile-missing")).toHaveText("2 of 15 (13.3%)");
  await expect(results.getByTestId("profile-duplicates")).toHaveText("1"); // row 3 = row 1
  // Mean of the valid temperatures, computed here independently: (-3.5 + 19 - 3.5 + 21.25) / 4.
  const mean = (-3.5 + 19 - 3.5 + 21.25) / 4;
  await expect(results.getByTestId("numeric-1")).toContainText(String(mean));
  await expect(results.getByTestId("column-2")).toContainText("date");

  const validation = page.getByRole("region", { name: "Validation" });
  await expect(validation.getByTestId("check-cell_accounting")).toContainText("Pass");
  await expect(validation.getByTestId("dataset-sha256")).toHaveText(
    createHash("sha256").update(CSV).digest("hex"),
  );
  await expect(page.locator(".chart .main-svg").first()).toBeVisible();
  await expect(page.locator(".chart")).toHaveCount(2);

  // Override temp_c to categorical: the stale notice appears until the profile is redone.
  await page.getByLabel("temp_c", { exact: true }).selectOption("categorical");
  await expect(results.getByRole("status")).toContainText("have changed since this profile");
  await page.getByRole("button", { name: "Profile again" }).click();
  await expect(results.getByRole("status")).toHaveCount(0);
  await expect(results.getByTestId("categorical-1")).toContainText("-3.5 (2)");

  await page.getByRole("link", { name: "Experiments" }).click();
  const row = page
    .getByRole("row")
    .filter({ hasText: /quant\.dataset_profile v1/ })
    .first();
  await expect(row).toContainText("5 rows × 3 columns, 2 missing cells, 1 duplicate rows");
  await expect(page.getByText("Oslo")).toHaveCount(0); // no data in the log
});

test("a malformed file is explained, not repaired", async ({ page }) => {
  await page.goto("/quant/datasets");
  await page.getByLabel("Upload a CSV file").check();
  await page.getByLabel(/^CSV file/).setInputFiles({
    name: "broken.csv",
    mimeType: "text/csv",
    buffer: Buffer.from("a,b,c\n1,2,3\n4,5\n6,7,8\n"),
  });
  await page.getByRole("button", { name: "Profile dataset" }).click();
  await expect(page.getByRole("form").getByRole("alert")).toContainText(
    "Every row must have 3 fields, like the header. 1 row(s) do not: row 2 (line 3) has 2.",
  );
  await expect(page.getByTestId("profile-rows")).toHaveCount(0);
});

test("a large file near the limit passes through the whole stack", async ({ page }) => {
  // About 1.9 MiB, 38,000 rows: under both the file and row limits.
  const rows = Array.from({ length: 38_000 }, (_, i) => `${i},label${i % 7},2026-01-05,0.5`);
  const csv = ["id,label,date,value", ...rows, ""].join("\n");
  expect(csv.length).toBeLessThan(2 * 1024 * 1024);
  await page.goto("/quant/datasets");
  await page.getByLabel("Upload a CSV file").check();
  await page.getByLabel(/^CSV file/).setInputFiles({
    name: "large.csv",
    mimeType: "text/csv",
    buffer: Buffer.from(csv),
  });
  await page.getByRole("button", { name: "Profile dataset" }).click();
  await expect(page.getByTestId("profile-rows")).toHaveText("38,000");
});

test("the messy sample flags mixed and ambiguous columns", async ({ page }) => {
  await page.goto("/quant/datasets");
  await page.getByRole("button", { name: "Profile dataset" }).click();
  await expect(page.getByTestId("profile-rows")).toHaveText("10");
  await expect(page.getByTestId("check-mixed_columns")).toContainText("2");
  await expect(page.getByTestId("column-4")).toContainText("cannot be known from the file");
});
