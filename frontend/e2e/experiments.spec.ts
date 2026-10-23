import { expect, test } from "@playwright/test";

// The experiment log end to end: run -> find it in the log -> replay it -> reopen it.
test("a saved run replays identically and reopens with its inputs", async ({ page }) => {
  await page.goto("/economy/solow");
  await page.getByLabel(/^New savings rate/).fill("0.33");
  await page.getByLabel(/^Policy year/).fill("7");
  await page.getByRole("button", { name: "Run model" }).click();
  // The run id is announced in the workspace's status line.
  const status = page.getByRole("status").filter({ hasText: "Showing run" });
  await expect(status).toBeAttached();
  const runId = (await status.textContent())!.match(/Showing run ([0-9a-f-]+)/)![1]!;

  await page.goto("/experiments");
  await page.getByRole("button", { name: "Economy" }).click();
  // Other E2E tests share this database: find this run by its id.
  const row = page.getByRole("row").filter({ has: page.locator(`code[title="${runId}"]`) });
  await expect(row).toContainText("k* ");
  await row.getByRole("button", { name: "Replay" }).click();
  await expect(page.getByText("Identical.")).toBeVisible();
  await expect(page.getByText(/bit-identical/)).toBeVisible();

  await row.getByRole("link", { name: "Open" }).click();
  await expect(page).toHaveURL(new RegExp(`/economy/solow\\?run=${runId}`));
  await expect(page.getByText(/Loaded the inputs of run/)).toBeVisible();
  await expect(page.getByLabel(/^New savings rate/)).toHaveValue("0.33");
  await expect(page.getByLabel(/^Policy year/)).toHaveValue("7");
});
