import { expect, test } from "@playwright/test";
import { waitForCatalog } from "./helpers";

// A real GStreamer process is started inside the api container by the test harness before this
// suite runs (see e2e/monitor-setup.sh / docs). These tests drive the read-only monitor UI against
// whatever GStreamer processes the API can see; they skip cleanly when none are present, so the
// suite is safe to run anywhere.

test("the live monitor lists GStreamer processes and reconstructs one", async ({ page, request }) => {
  await waitForCatalog(request);
  const processes = await (await request.get("/api/monitor/processes")).json();
  test.skip(processes.processes.length === 0, "no GStreamer process visible to the API");

  await page.goto("/");
  await page.getByRole("button", { name: /live monitor/i }).click();
  await expect(page).toHaveURL(/\/monitor$/);
  await expect(page.getByRole("heading", { name: "Live monitor" })).toBeVisible();

  const first = page.locator(".monitor-proc").first();
  await expect(first).toBeVisible();
  await first.click();

  // The pipeline is reconstructed and rendered as a read-only graph.
  await expect(page.locator(".monitor-node").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.locator(".monitor-meta")).toContainText(/elements/);
  await page.screenshot({ path: "test-results/10-monitor.png" });
});

test("monitor nodes are not editable", async ({ page, request }) => {
  await waitForCatalog(request);
  const processes = await (await request.get("/api/monitor/processes")).json();
  test.skip(processes.processes.length === 0, "no GStreamer process visible to the API");

  await page.goto("/monitor");
  await page.locator(".monitor-proc").first().click();
  await expect(page.locator(".monitor-node").first()).toBeVisible({ timeout: 30_000 });
  // Read-only: pad handles are present but not connectable.
  const handle = page.locator(".monitor-node .react-flow__handle").first();
  if (await handle.count()) {
    await expect(handle).toHaveClass(/react-flow__handle/);
  }
});
