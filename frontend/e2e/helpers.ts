import { type Locator, type Page, expect } from "@playwright/test";

/** The id of the run just shown, read from the workspace's status line. */
export async function shownRunId(page: Page): Promise<string> {
  const status = page.getByRole("status").filter({ hasText: "Showing run" });
  await expect(status).toBeAttached();
  return (await status.textContent())!.match(/Showing run ([0-9a-f-]+)/)![1]!;
}

/** This run's row in the experiment log. E2E tests share one database and run in parallel,
 *  so a test must find its own run by id, never "the newest row". */
export function logRow(page: Page, runId: string): Locator {
  return page.getByRole("row").filter({ has: page.locator(`code[title="${runId}"]`) });
}
