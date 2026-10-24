import { expect, test } from "@playwright/test";
import { cleanup, connect, createProject, node, openEditor, track, waitForCatalog } from "./helpers";

test.afterEach(async ({ request }) => cleanup(request));

test("create a pipeline from a template", async ({ page, request }) => {
  await waitForCatalog(request);
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Pipelab" })).toBeVisible();
  await page.getByRole("button", { name: "New pipeline" }).first().click();
  await page.getByRole("dialog").locator("input").first().fill("E2E template");
  await page.locator(".template-option", { hasText: "Video test pattern" }).click();
  await page.getByRole("dialog").getByRole("button", { name: /create/i }).click();
  await expect(page).toHaveURL(/\/projects\//);
  track(page.url().split("/projects/")[1]);
  await expect(page.locator(".react-flow__node")).toHaveCount(5);
  await page.screenshot({ path: "test-results/01-editor-template.png" });
});

test("run, preview, change a property live and stop", async ({ page, request }) => {
  const id = await createProject(request, { name: "E2E run", template: "video-test" });
  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);
  await page.getByRole("tab", { name: /preview/i }).click();
  const frame = page.locator(".preview-tile img").first();
  await expect(frame).toHaveAttribute("src", /^blob:/);
  await node(page, "videotestsrc").click();
  await page.screenshot({ path: "test-results/02-running-preview.png" });
  await page.locator(".palette-item", { hasText: "fakesink" }).first().dblclick();
  await expect(page.getByRole("button", { name: /restart/i })).toBeVisible();
  await page.getByRole("button", { name: "Stop" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/stopped/, { timeout: 30_000 });
});

test("incompatible links are blocked and a bridge can be inserted", async ({ page, request }) => {
  const id = await createProject(request, {
    name: "E2E connect",
    graph: {
      nodes: [
        { id: "a", factory: "videotestsrc", name: "src", properties: {}, position: { x: 0, y: 0 } },
        { id: "b", factory: "rtph264pay", name: "pay", properties: {}, position: { x: 420, y: 0 } },
      ],
      edges: [],
    },
  });
  await openEditor(page, id);
  await page.waitForTimeout(800); // initial fit-view animation
  await connect(page, "src", "src", "pay", "sink");
  const suggestion = page.getByRole("button", { name: "Insert x264enc" }).first();
  await expect(suggestion).toBeVisible();
  await page.screenshot({ path: "test-results/03-blocked-link.png" });
  await suggestion.click();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await expect(page.locator(".react-flow__edge")).toHaveCount(2);
});

test("export the pipeline and import a gst-launch line", async ({ page, request }) => {
  const id = await createProject(request, { name: "E2E export", template: "record-mp4" });
  await openEditor(page, id);
  await page.getByRole("button", { name: /export/i }).first().click();
  await expect(page.getByRole("dialog")).toContainText("gst-launch-1.0");
  await page.screenshot({ path: "test-results/04-export.png" });
  await page.keyboard.press("Escape");

  await page.goto("/");
  await page.getByRole("button", { name: /import/i }).first().click();
  await page.getByRole("dialog").locator("textarea").fill("videotestsrc num-buffers=10 ! videoconvert ! fakesink");
  await page.getByRole("dialog").getByRole("button", { name: /import|create/i }).last().click();
  await expect(page).toHaveURL(/\/projects\//);
  track(page.url().split("/projects/")[1]);
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
});
