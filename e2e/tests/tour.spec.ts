import { expect, test, type Page } from "@playwright/test";
import { cleanup, createProject, node, openEditor } from "./helpers";

test.afterEach(async ({ request }) => cleanup(request));

const tab = (page: Page, name: RegExp) => page.getByRole("tab", { name });

test("live switching of an input-selector and watching a link", async ({ page, request }) => {
  const id = await createProject(request, { name: "Tour selector", template: "input-selector" });
  const graph = (await (await request.get(`/api/projects/${id}`)).json()).graph;
  const selector = graph.nodes.find((n: { factory: string }) => n.factory === "input-selector");
  const output = graph.edges.find((e: { source: string }) => e.source === selector.id);

  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);

  const selectorNode = page.locator(`[data-testid="rf__node-${selector.id}"]`);
  const into = (pad: string) => graph.edges.find((e: { target: string; target_pad: string }) =>
    e.target === selector.id && e.target_pad === pad);
  const edgePath = (edgeId: string) => page.locator(`[data-testid="rf__edge-${edgeId}"] .flow-edge`);
  // GStreamer picks sink_0 by itself; the runtime reports it and the other input is shown as dropped.
  await expect(selectorNode.getByRole("radio", { name: "Make sink_0 the active pad" })).toHaveAttribute("aria-checked", "true");
  await expect(edgePath(into("sink_1").id)).toHaveClass(/discarded/);

  await selectorNode.getByRole("radio", { name: "Make sink_1 the active pad" }).click();
  await expect
    .poll(async () => (await (await request.get(`/api/projects/${id}/runtime/properties/${selector.id}`)).json())
      .properties["active-pad"])
    .toBe("sink_1");
  await expect(edgePath(into("sink_0").id)).toHaveClass(/discarded/);
  await expect(edgePath(into("sink_1").id)).not.toHaveClass(/discarded/);
  await expect(page.getByRole("button", { name: /restart/i })).toHaveCount(0);

  await page.locator(`[data-testid="rf__edge-${output.id}"]`).click({ force: true });
  await page.locator("label.switch", { has: page.getByRole("checkbox", { name: "Watch this link" }) }).click();
  await tab(page, /preview/i).click();
  await expect(page.locator(".preview-tile img")).toHaveCount(2);
  await page.screenshot({ path: "test-results/05-selector-and-tap.png" });
});

test("runtime errors point at the failing element with a hint", async ({ page, request }) => {
  const id = await createProject(request, {
    name: "Tour error",
    graph: {
      nodes: [
        { id: "f", factory: "filesrc", name: "missing_file", properties: { location: "nope.mp4" }, position: { x: 0, y: 0 } },
        { id: "s", factory: "fakesink", name: "sink", properties: {}, position: { x: 320, y: 0 } },
      ],
      edges: [{ id: "e", source: "f", source_pad: "src", target: "s", target_pad: "sink" }],
    },
  });
  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/error/);
  await tab(page, /bus/i).click();
  const line = page.locator(".bus-line", { hasText: "Resource not found" }).first();
  await line.click();
  await expect(page.locator(".bus-hint").first()).toContainText("location");
  await expect(node(page, "missing_file").locator(".element-node")).toHaveClass(/status-error/);
  await page.screenshot({ path: "test-results/06-runtime-error.png" });
});

test("files produced by a pipeline can be played from Outputs", async ({ page, request }) => {
  const id = await createProject(request, { name: "Tour record", template: "record-mp4" });
  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/stopped/, { timeout: 60_000 });
  await tab(page, /outputs/i).click();
  await page.locator(".output-row", { hasText: "test.mp4" }).click();
  await expect(page.locator(".outputs-player video")).toBeVisible();
  await page.screenshot({ path: "test-results/07-outputs.png" });
});

test("inspector, python export and light theme", async ({ page, request }) => {
  const id = await createProject(request, { name: "Tour export", template: "tee-preview-record" });
  await openEditor(page, id);
  await node(page, "x264enc").click();
  await expect(page.getByRole("combobox", { name: "tune" })).toBeVisible();
  await page.screenshot({ path: "test-results/08-inspector.png" });
  await page.getByRole("button", { name: /export/i }).first().click();
  await page.getByRole("dialog").getByRole("tab", { name: /python/i }).click();
  await expect(page.getByRole("dialog")).toContainText("Gst.ElementFactory.make");
  await page.screenshot({ path: "test-results/09-export-python.png" });
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await page.screenshot({ path: "test-results/10-light-theme.png" });
});

test("probing a link lists its buffers and events", async ({ page, request }) => {
  const id = await createProject(request, { name: "Tour probe", template: "video-test" });
  const graph = (await (await request.get(`/api/projects/${id}`)).json()).graph;
  const first = graph.edges[0];
  await openEditor(page, id);
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);
  await page.locator(`[data-testid="rf__edge-${first.id}"]`).click({ force: true });
  await page.locator(".edge-toolbar").getByRole("button", { name: /probe/i }).click();
  await expect(tab(page, /probe/i)).toHaveAttribute("aria-selected", "true");
  await expect.poll(async () => page.locator("tr.probe-row.buffer").count()).toBeGreaterThan(5);
  await expect(page.locator(".probe-summary")).toContainText("buf/s");
  await page.screenshot({ path: "test-results/11-probe.png" });
});

test("the palette groups elements by category", async ({ page, request }) => {
  const id = await createProject(request, { name: "Tour palette", template: "video-test" });
  await openEditor(page, id);
  const sources = page.locator(".palette-group-header", { hasText: "Sources" });
  await expect(sources).toBeVisible();
  await expect(page.locator(".palette-group-header", { hasText: "Encoders" })).toBeVisible();
  if ((await sources.getAttribute("aria-expanded")) !== "true") await sources.click();
  await expect(page.locator(".group-sources .palette-item", { hasText: "audiotestsrc" }).first()).toBeVisible();
  await page.screenshot({ path: "test-results/12-palette-groups.png" });
});
