// Screenshots of the user manual (docs/manual/images). Not part of the test suite: run with
// `make docs GPU=1` (NVIDIA elements appear as available), which sets DOCS_DIR and mounts
// docs/manual/images there.

import { expect, test, type Locator, type Page } from "@playwright/test";
import { cleanup, connect, createProject, node, openEditor, waitForCatalog, type Graph } from "./helpers";

const DOCS_DIR = process.env.DOCS_DIR;
const STARTER = "h264-encoder";
const GROUPED = "docs-test-source";

test.skip(!DOCS_DIR, "manual screenshots: run with make docs");
test.describe.configure({ mode: "serial" });
// Sharper images and a slightly smaller window, so nodes stay readable in the manual.
test.use({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1.5 });

test.afterEach(async ({ request }) => {
  await cleanup(request);
  for (const id of [STARTER, GROUPED]) await request.delete(`/api/components/${id}`);
});

interface ShotOptions {
  /** Leave the pointer where it is (popups that close when it moves). */
  keepPointer?: boolean;
  /** Keep notifications (some feedback, e.g. a refused link, is one). */
  keepToasts?: boolean;
  /** Only the top part of the window, in CSS pixels. */
  height?: number;
}

async function shot(page: Page, name: string, target?: Locator, options: ShotOptions = {}): Promise<void> {
  if (!options.keepPointer) await page.mouse.move(0, 0);
  if (!options.keepToasts) await page.addStyleTag({ content: ".toasts { display: none !important; }" });
  await page.waitForTimeout(300);
  const path = `${DOCS_DIR}/${name}.png`;
  const view = page.viewportSize()!;
  const clip = options.height ? { x: 0, y: 0, width: view.width, height: options.height } : undefined;
  await (target ? target.screenshot({ path }) : page.screenshot({ path, clip }));
}

/** A region around an element (e.g. the floating toolbar of a link) with some context. */
async function shotAround(page: Page, name: string, target: Locator, margin = { x: 260, y: 140 }): Promise<void> {
  const box = (await target.boundingBox())!;
  const view = page.viewportSize()!;
  const x = Math.max(0, box.x - margin.x);
  const y = Math.max(0, box.y - margin.y);
  await page.mouse.move(0, 0);
  await page.waitForTimeout(300);
  await page.screenshot({
    path: `${DOCS_DIR}/${name}.png`,
    clip: { x, y, width: Math.min(view.width - x, box.width + 2 * margin.x), height: Math.min(view.height - y, box.height + 2 * margin.y) },
  });
}

async function imported(page: Page, name: string, description: string): Promise<string> {
  await waitForCatalog(page.request);
  const response = await page.request.post("/api/import/gst-launch", { data: { description } });
  const graph = (await response.json()).graph as Graph;
  return createProject(page.request, { name, graph });
}

async function play(page: Page, state = /playing/): Promise<void> {
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(state);
}

const tab = (page: Page, name: RegExp) => page.getByRole("tab", { name });

test("docs: projects and templates", async ({ page, request }) => {
  await createProject(request, { name: "Lobby camera", template: "input-selector" });
  await createProject(request, { name: "Recorder", template: "record-mp4" });
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Pipelab" })).toBeVisible();
  await shot(page, "projects", undefined, { height: 420 });
  await page.getByRole("button", { name: "New pipeline" }).first().click();
  await expect(page.locator(".template-option").first()).toBeVisible();
  await shot(page, "new-pipeline", page.getByRole("dialog"));
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: /import/i }).first().click();
  await page.getByRole("dialog").locator("textarea")
    .fill("rtspsrc location=rtsp://camera/stream latency=200 ! rtph264depay ! h264parse ! avdec_h264 ! videoconvert ! autovideosink");
  await shot(page, "import-launch", page.getByRole("dialog"));
});

test("docs: editor, palette and inspector", async ({ page, request }) => {
  const overview = await createProject(request, { name: "Input selector", template: "input-selector" });
  await openEditor(page, overview);
  await shot(page, "editor");
  const id = await createProject(request, { name: "Preview and record", template: "tee-preview-record" });
  await openEditor(page, id);
  await page.getByPlaceholder(/Search/).fill("h264");
  await shot(page, "palette-search", page.locator(".palette"));
  await page.getByPlaceholder(/Search/).fill("");
  await node(page, "x264enc").click();
  await expect(page.getByRole("combobox", { name: "tune" })).toBeVisible();
  await shot(page, "inspector", page.locator(".inspector"));
});

test("docs: validation and fixes", async ({ page }) => {
  const id = await createProject(page.request, {
    name: "Linking",
    graph: {
      nodes: [
        { id: "a", factory: "videotestsrc", name: "src", properties: {}, position: { x: 0, y: 0 } },
        { id: "b", factory: "rtph264pay", name: "pay", properties: {}, position: { x: 420, y: 0 } },
      ],
      edges: [],
    },
  });
  await openEditor(page, id);
  await page.waitForTimeout(800);
  await connect(page, "src", "src", "pay", "sink");
  await expect(page.getByRole("button", { name: "Insert x264enc" }).first()).toBeVisible();
  await shot(page, "link-blocked", undefined, { keepPointer: true, keepToasts: true });

  const tee = await imported(page, "Tee without queues",
    "videotestsrc ! tee name=t ! videoconvert ! autovideosink t. ! x264enc ! mp4mux ! filesink location=out.mp4");
  await openEditor(page, tee);
  await tab(page, /issues/i).click();
  await expect(page.locator(".issues-panel")).toContainText(/queue/i);
  await shot(page, "issues");
});

test("docs: running, previews and live properties", async ({ page, request }) => {
  const id = await createProject(request, { name: "Input selector", template: "input-selector" });
  await openEditor(page, id);
  await play(page);
  await tab(page, /preview/i).click();
  await expect(page.locator(".preview-tile img").first()).toHaveAttribute("src", /^blob:/);
  const selector = page.locator(".react-flow__node", { has: page.getByRole("radio", { name: /active pad/ }) }).first();
  await page.waitForTimeout(1500);
  await shot(page, "running");
  await selector.click();
  await shot(page, "live-properties", page.locator(".inspector"));
  await tab(page, /bus/i).click();
  await shot(page, "bus", page.locator(".dock"));
  await page.getByRole("button", { name: "Runtime graph" }).click();
  await expect(page.getByRole("dialog").locator("svg").first()).toBeVisible({ timeout: 30_000 });
  await shot(page, "runtime-graph", page.getByRole("dialog"));
});

test("docs: watching and probing links", async ({ page, request }) => {
  const id = await createProject(request, { name: "Test pattern", template: "video-test" });
  const graph = (await (await request.get(`/api/projects/${id}`)).json()).graph as Graph;
  await openEditor(page, id);
  await play(page);
  const link = page.locator(`[data-testid="rf__edge-${graph.edges[1].id}"]`);
  await link.click({ force: true });
  await expect(page.locator(".edge-toolbar")).toBeVisible();
  await shotAround(page, "link-toolbar", page.locator(".edge-toolbar"), { x: 420, y: 120 });
  await page.locator(".edge-toolbar").getByRole("button", { name: /watch/i }).click();
  await page.locator(".edge-toolbar").getByRole("button", { name: /probe/i }).click();
  await expect.poll(async () => page.locator("tr.probe-row.buffer").count()).toBeGreaterThan(5);
  await shot(page, "probe", page.locator(".dock"));
  await tab(page, /preview/i).click();
  await expect(page.locator(".preview-tile img")).toHaveCount(2);
  await shot(page, "watch", page.locator(".dock"));
});

test("docs: runtime errors", async ({ page, request }) => {
  const id = await createProject(request, {
    name: "Missing file",
    graph: {
      nodes: [
        { id: "f", factory: "filesrc", name: "camera_dump", properties: { location: "missing.mp4" }, position: { x: 0, y: 0 } },
        { id: "d", factory: "decodebin", name: "decoder", properties: {}, position: { x: 320, y: 0 } },
        { id: "s", factory: "fakesink", name: "sink", properties: {}, position: { x: 640, y: 0 } },
      ],
      edges: [
        { id: "e1", source: "f", source_pad: "src", target: "d", target_pad: "sink" },
        { id: "e2", source: "d", source_pad: "src_%u", target: "s", target_pad: "sink" },
      ],
    },
  });
  await openEditor(page, id);
  await play(page, /error/);
  await tab(page, /bus/i).click();
  await page.locator(".bus-line", { hasText: "Resource not found" }).first().click();
  await expect(page.locator(".bus-hint").first()).toBeVisible();
  await shot(page, "runtime-error");
});

test("docs: performance", async ({ page }) => {
  const id = await imported(page, "Slow branch",
    "videotestsrc is-live=true ! video/x-raw,width=640,height=360,framerate=30/1 ! queue name=q max-size-buffers=5 " +
    "max-size-time=0 max-size-bytes=0 ! identity name=slow sleep-time=50000 ! videoconvert ! autovideosink");
  await openEditor(page, id);
  await play(page);
  await expect(node(page, "q").locator(".queue-meter.level-error")).toBeVisible({ timeout: 15_000 });
  await tab(page, /performance/i).click();
  await page.getByLabel("Colour links by thread").check();
  await expect(page.locator(".perf-panel td").filter({ hasText: /^\d+\.\d%$/ }).first()).toBeVisible({ timeout: 15_000 });
  await shot(page, "performance");
});

test("docs: components", async ({ page }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  const id = await imported(page, "Components",
    "videotestsrc is-live=true pattern=ball name=src ! capsfilter name=caps caps=video/x-raw,width=640,height=360 " +
    "! queue ! videoconvert ! autovideosink");
  await openEditor(page, id);
  await node(page, "src").click();
  await node(page, "caps").click({ modifiers: ["Shift"] });
  await page.getByRole("button", { name: "Group into component" }).click();
  const group = page.getByRole("dialog", { name: "Group into component" });
  await group.getByLabel("Name").fill("Docs test source");
  await shot(page, "component-group", group);
  await group.getByRole("button", { name: "Group" }).click();
  await expect(group).toBeHidden();
  const instance = page.locator(".react-flow__node").filter({ has: page.locator(".component-glyph") });
  await instance.click();
  await shot(page, "component-instance");

  await instance.dblclick();
  await expect(page.getByRole("navigation", { name: "Component breadcrumbs" })).toBeVisible();
  await node(page, "src").click();
  await page.getByRole("button", { name: "Expose pattern as parameter" }).click();
  await page.getByRole("dialog").getByRole("button", { name: "Expose" }).click();
  await page.locator(".react-flow__pane").click({ position: { x: 120, y: 420 } });
  await shot(page, "component-inside");
  await page.getByRole("button", { name: /Save component/ }).click();
  await page.getByRole("navigation", { name: "Component breadcrumbs" }).getByRole("button", { name: "Components" }).click();

  await page.getByRole("button", { name: "Starters…" }).click();
  const starters = page.getByRole("dialog", { name: "Starter components" });
  await starters.getByRole("button", { name: "Add H.264 encoder", exact: true }).click();
  await expect(starters.getByRole("button", { name: "Add H.264 encoder", exact: true })).toHaveText("In the library");
  await shot(page, "starters", starters);
});

test("docs: export", async ({ page, request }) => {
  const id = await createProject(request, { name: "Preview and record", template: "tee-preview-record" });
  await openEditor(page, id);
  await page.getByRole("button", { name: /export/i }).first().click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("gst-launch-1.0");
  await shot(page, "export-launch", dialog);
  await dialog.getByRole("tab", { name: /rust/i }).click();
  await expect(dialog).toContainText("gstreamer");
  await shot(page, "export-rust", dialog);
});

test("docs: outputs and theme", async ({ page, request }) => {
  const id = await createProject(request, { name: "Recorder", template: "record-mp4" });
  await openEditor(page, id);
  await play(page, /stopped/);
  await tab(page, /outputs/i).click();
  await page.locator(".output-row", { hasText: "test.mp4" }).click();
  await expect(page.locator(".outputs-player video")).toBeVisible();
  await shot(page, "outputs", page.locator(".dock"));
  await page.getByRole("button", { name: "Toggle theme" }).click();
  await shot(page, "light-theme");
  await page.getByRole("button", { name: "Toggle theme" }).click();
});
