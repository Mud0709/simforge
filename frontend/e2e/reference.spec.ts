import { readFile } from "node:fs/promises";

import { expect, test } from "@playwright/test";

import { logRow, shownRunId } from "./helpers";

// Roadmap 1.6 end to end: run and save -> pin it as the reference run -> change one input and
// run again -> faded overlay and comparison table -> CSV download -> reload recomputes the
// reference from the log -> JSON export of the run from the experiment log. Its runs use
// input values no other test uses, and are found by run id, so parallel tests cannot clash.
test("pin a reference run, compare a new run with it, and export both ways", async ({ page }) => {
  await page.goto("/economy/solow");
  await page.getByLabel(/^New savings rate/).fill("0.31");
  await page.getByLabel(/^Policy year/).fill("12");
  await page.getByRole("button", { name: "Run model" }).click();
  const referenceId = await shownRunId(page);

  const reference = page.getByRole("region", { name: "Reference run" });
  await reference.getByRole("button", { name: "Pin as reference run" }).click();
  await expect(page).toHaveURL(new RegExp(`[?&]ref=${referenceId}`));
  await expect(reference.getByTestId("reference-provenance")).toContainText(
    "computed in this session",
  );

  await page.getByLabel(/^New savings rate/).fill("0.36");
  await page.getByRole("button", { name: "Run model" }).click();
  await expect
    .poll(async () => shownRunId(page), { message: "a second run is shown" })
    .not.toBe(referenceId);
  const runId = await shownRunId(page);

  // The reference's curves, faded and dashed, under the new run's on the capital chart.
  const capital = page.getByRole("img", { name: "Capital per effective worker over time" });
  await expect(capital.locator(".legendtext", { hasText: "reference run" })).toBeVisible();
  const faded = await capital.evaluate((el) =>
    (
      el as unknown as { data: { name?: string; opacity?: number; line?: { dash?: string } }[] }
    ).data
      .filter((t) => t.name === "reference run")
      .map((t) => ({ opacity: t.opacity, dash: t.line?.dash })),
  );
  expect(faded.length).toBe(2); // the reference's baseline and scenario paths
  for (const t of faded) {
    expect(t.opacity).toBeLessThan(1);
    expect(t.dash).toBe("dash");
  }

  // Only the changed input is listed, with both values as typed.
  const inputs = reference.getByRole("table", { name: /Inputs that differ/ });
  await expect(inputs.locator("tbody tr")).toHaveCount(1);
  const changed = inputs.locator("tbody tr").first();
  await expect(changed.locator("th")).toHaveText("policy.new_savings_rate");
  await expect(changed.locator("td")).toHaveText(["0.31", "0.36"]);
  // The baseline does not depend on the policy, so its steady state is exactly unchanged.
  const summary = reference.getByRole("table", { name: /Summary: reference run and this run/ });
  const baseline = summary.locator("tbody tr", {
    has: page.locator("code", { hasText: /^baseline_steady_state_capital$/ }),
  });
  await expect(baseline.locator("td").nth(2)).toHaveText("0");

  // The CSV is made in the browser from the run on screen.
  const csvDownload = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download baseline and scenario paths (CSV)" }).click();
  const csv = await csvDownload;
  expect(csv.suggestedFilename()).toBe(`economy.solow_${runId.slice(0, 8)}_paths.csv`);
  const text = await readFile((await csv.path())!, "utf8");
  // Header: `name [unit]` with the Solow units (economy/solow/model.py), quoted where the
  // text holds a comma (RFC 4180).
  const header = [
    "year [year]",
    ...["baseline", "scenario"].flatMap((p) => [
      `"${p}_capital [capital per effective worker (model units, A_0 = L_0 = 1)]"`,
      `${p}_output [output per effective worker per year (model units)]`,
      `${p}_consumption [consumption per effective worker per year (model units)]`,
      `${p}_investment [investment per effective worker per year (model units)]`,
      `${p}_savings_rate [fraction of output]`,
      `"${p}_output_per_worker_index [index, year 0 = 100]"`,
      `${p}_output_per_worker_growth [fraction per year]`,
    ]),
  ].join(",");
  expect(text.split(/\r?\n/)[0]).toBe(header);

  // A reload keeps ?ref= and recomputes the reference from the experiment log.
  await page.reload();
  await expect(reference.getByTestId("reference-provenance")).toHaveText(
    "recomputed, bit-identical",
  );

  // The saved run's record, as a versioned JSON export from the log.
  await page.goto("/experiments");
  await page.getByRole("button", { name: "Economy" }).click();
  const row = logRow(page, runId);
  const jsonDownload = page.waitForEvent("download");
  await row.getByRole("link", { name: "Export JSON" }).click();
  const json = await jsonDownload;
  expect(json.suggestedFilename()).toBe(`economy.solow_${runId.slice(0, 8)}.json`);
  const exported = JSON.parse(await readFile((await json.path())!, "utf8")) as {
    export_version: number;
    record: { run_id: string; inputs: { policy: { new_savings_rate: number } } };
  };
  expect(exported.export_version).toBe(1);
  expect(exported.record.run_id).toBe(runId);
  expect(exported.record.inputs.policy.new_savings_rate).toBe(0.36);
});
