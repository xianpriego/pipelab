import { expect, test } from "@playwright/test";
import { cleanup, createProject, node, openEditor, waitForCatalog, type Graph } from "./helpers";

test.afterEach(async ({ request }) => cleanup(request));

test("the Performance tab finds the slow branch behind a full queue", async ({ page, request }) => {
  await waitForCatalog(request);
  const imported = await request.post("/api/import/gst-launch", { data: { description:
    "videotestsrc is-live=true ! video/x-raw,width=320,height=240,framerate=30/1 ! queue name=q max-size-buffers=5 " +
    "max-size-time=0 max-size-bytes=0 ! identity name=slow sleep-time=50000 ! videoconvert ! autovideosink" } });
  const graph = (await imported.json()).graph as Graph;
  const id = await createProject(request, { name: "E2E perf", graph });
  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);

  // On the canvas: the queue shows its level, the slow element its time per buffer.
  await expect(node(page, "q").locator(".queue-meter.level-error")).toBeVisible({ timeout: 10_000 });
  await expect(node(page, "slow").locator(".node-perf-text")).toContainText(/⏱ [4-9]\d(\.\d)? ms/);

  await page.getByRole("tab", { name: /Performance/ }).click();
  await expect(page.locator(".perf-insights")).toContainText("q is 100% full");
  await expect(page.locator(".perf-panel")).toContainText("videotestsrc0:src");
  await expect(page.locator(".flow-edge.by-thread")).toHaveCount(0);
  await page.getByLabel("Colour links by thread").check();
  await expect(page.locator(".flow-edge.by-thread")).toHaveCount(5);
  await expect(page.locator(".perf-panel td").filter({ hasText: "%" }).first()).toBeVisible();
  await page.screenshot({ path: "test-results/perf.png" });
  await page.locator(".perf-insights li").first().click();
  await expect(node(page, "q")).toHaveClass(/selected/);
});
