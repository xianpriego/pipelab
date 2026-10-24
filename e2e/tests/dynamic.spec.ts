import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { cleanup, createProject, node, openEditor, waitForCatalog, type Graph } from "./helpers";

// Slots, API functions, probe rules and scripts are hidden unless the web image is built with
// VITE_PIPELAB_ADVANCED=1; run these tests against such a build with ADVANCED_UI=1.
const advanced = process.env.ADVANCED_UI === "1";

const components: string[] = [];

test.afterEach(async ({ request }) => {
  await cleanup(request);
  while (components.length) await request.delete(`/api/components/${components.pop()}`);
});

async function importProject(request: APIRequestContext, name: string, description: string) {
  await waitForCatalog(request);
  const imported = await request.post("/api/import/gst-launch", { data: { description } });
  expect(imported.ok()).toBeTruthy();
  const graph = (await imported.json()).graph as Graph;
  return { id: await createProject(request, { name, graph }), graph };
}

/** A live test source exposed as port "src", with its pattern as parameter. */
async function createSourceComponent(request: APIRequestContext, id: string) {
  const response = await request.put(`/api/components/${id}`, {
    data: {
      id, name: "E2E test source", description: "videotestsrc for slots", version: 0,
      graph: {
        nodes: [{
          id: "s", factory: "videotestsrc", name: "s", properties: { "is-live": true }, pad_properties: {},
          position: { x: 0, y: 0 }, preview: "auto",
        }],
        edges: [],
      },
      ports: [{ name: "src", direction: "src", node_id: "s", pad: "src" }],
      parameters: [{ name: "pattern", description: "Test pattern", default: 0, targets: [{ node_id: "s", property: "pattern" }] }],
    },
  });
  expect(response.ok()).toBeTruthy();
  components.push(id);
}

async function play(page: Page) {
  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);
}

test("groups two elements into a component, enters it and comes back", async ({ page, request }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  const stamp = Date.now();
  const { id } = await importProject(request, "E2E group", "videotestsrc is-live=true ! videoconvert name=conv ! queue name=buf ! fakesink");
  await openEditor(page, id);
  await node(page, "conv").click();
  await node(page, "buf").click({ modifiers: ["Shift"] });
  await page.getByRole("button", { name: "Group into component" }).click();
  const dialog = page.getByRole("dialog", { name: "Group into component" });
  await dialog.getByLabel("Name").fill(`E2E group ${stamp}`);
  components.push(`e2e-group-${stamp}`);
  await dialog.getByRole("button", { name: "Group" }).click();
  await expect(dialog).toBeHidden();

  const instance = page.locator(".react-flow__node").filter({ has: page.locator(".component-glyph") });
  await expect(instance).toHaveCount(1);
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await page.screenshot({ path: "test-results/dynamic-grouped.png" });

  const validated = page.waitForResponse((response) => response.url().endsWith("/api/components/validate"));
  await instance.dblclick();
  const crumbs = page.getByRole("navigation", { name: "Component breadcrumbs" });
  await expect(crumbs).toContainText(`E2E group ${stamp}`);
  await expect(node(page, "conv")).toBeVisible();
  await expect(page.locator(".react-flow__node")).toHaveCount(2);
  await expect(page.locator(".port-marker")).toHaveCount(2);
  // Inside the component the definition is validated, not the project (videotestsrc0 is outside).
  expect((await validated).status()).toBe(200);
  await expect(page.getByText(/videotestsrc0/)).toHaveCount(0);
  await expect(page.getByText(/Validation unavailable/)).toHaveCount(0);
  await page.screenshot({ path: "test-results/dynamic-inside-component.png" });

  await crumbs.getByRole("button", { name: "E2E group", exact: true }).click();
  await expect(crumbs).toBeHidden();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await expect(instance).toHaveCount(1);
});

test("a slot on a compositor starts one instance and adds/removes others live", async ({ page, request }) => {
  test.skip(!advanced, "advanced UI disabled");
  page.on("dialog", (dialog) => void dialog.accept());
  const component = `e2e-src-${Date.now()}`;
  await createSourceComponent(request, component);
  const { id } = await importProject(request, "E2E slot", "compositor name=mix ! videoconvert ! fakesink");
  await openEditor(page, id);
  await node(page, "mix").click();
  await page.getByLabel("Component of the new slot").selectOption(component);
  await page.getByRole("button", { name: "Add slot" }).click();

  const slotNode = page.locator(".slot-node");
  await expect(slotNode).toBeVisible();
  await expect(page.locator(".react-flow__edge.slot-link")).toHaveCount(1);
  await page.getByRole("button", { name: "Edit slot…" }).click();
  const editor = page.getByRole("dialog", { name: /^Slot / });
  await editor.getByRole("button", { name: "Initial instance" }).click();
  await editor.getByRole("button", { name: "Save" }).click();
  await expect(editor).toBeHidden();
  await expect(slotNode.locator(".slot-count")).toHaveText("×1");

  await play(page);
  const live = page.getByRole("list", { name: /Live instances of/ }).getByRole("listitem");
  await expect(live).toHaveCount(1);
  for (let i = 0; i < 2; i += 1) {
    await page.getByRole("button", { name: "Add", exact: true }).click();
    const add = page.getByRole("dialog", { name: /^Add / });
    await add.getByRole("button", { name: "Add instance" }).click();
    await expect(add).toBeHidden();
  }
  await expect(live).toHaveCount(3);
  await expect(slotNode.locator(".slot-count")).toHaveText("×3");
  await expect(slotNode.locator(".slot-rate")).toContainText(/src: 3 flowing · \d+/);
  await page.screenshot({ path: "test-results/dynamic-slot-live.png" });

  await page.getByRole("button", { name: /^Remove / }).first().click();
  await expect(live).toHaveCount(2);
  await expect(page.locator(".state-pill")).toHaveText(/playing/);
});

test("a watchdog probe posts branch-down when its link stops flowing", async ({ page, request }) => {
  test.skip(!advanced, "advanced UI disabled");
  page.on("dialog", (dialog) => void dialog.accept());
  const { id, graph } = await importProject(request, "E2E watchdog",
    "videotestsrc is-live=true num-buffers=30 name=src ! fakesink name=out audiotestsrc is-live=true ! fakesink name=keep");
  const edge = graph.edges.find((e) => graph.nodes.find((n) => n.id === e.source)?.name === "src")!;
  await openEditor(page, id);
  await page.locator(`[data-testid="rf__edge-${edge.id}"] .react-flow__edge-interaction`).dispatchEvent("click");
  await page.getByRole("button", { name: "Add probe" }).click();
  await page.getByRole("listitem").filter({ hasText: "Watchdog" }).click();
  const dialog = page.getByRole("dialog", { name: /probe on/i });
  await expect(dialog.getByRole("region", { name: "Rule 1" })).toBeVisible();
  await page.screenshot({ path: "test-results/dynamic-watchdog-editor.png" });
  await dialog.getByRole("button", { name: "Cancel" }).click();
  await expect(page.locator(".probe-badge").first()).toBeVisible();

  await play(page);
  await page.getByRole("tab", { name: /bus/i }).click();
  await page.getByLabel("Message kind").selectOption("application");
  await expect(page.locator(".bus-row.kind-application").filter({ hasText: "branch-down" }).first())
    .toBeVisible({ timeout: 20_000 });
  await page.screenshot({ path: "test-results/dynamic-watchdog-bus.png" });
});

test("a custom API function is defined in the API tab and called live", async ({ page, request }) => {
  test.skip(!advanced, "advanced UI disabled");
  page.on("dialog", (dialog) => void dialog.accept());
  const { id, graph } = await importProject(request, "E2E api", "videotestsrc is-live=true name=src ! fakesink");
  const src = graph.nodes.find((n) => n.name === "src")!;
  await openEditor(page, id);
  await page.getByRole("tab", { name: "API" }).click();
  await page.getByRole("button", { name: "New function" }).click();
  const dialog = page.getByRole("dialog", { name: "New API function" });
  await dialog.getByLabel("Name", { exact: true }).fill("set_pattern");
  await dialog.getByRole("button", { name: "Parameter" }).click();
  await dialog.getByLabel("Parameter 1 name").fill("pattern");
  await dialog.getByLabel("Parameter 1 type").selectOption("int");
  await dialog.getByRole("button", { name: "Action", exact: true }).click();
  await dialog.getByLabel("set_pattern action 1", { exact: true }).selectOption("set-property");
  await dialog.getByLabel("Element", { exact: true }).fill("src");
  await dialog.getByLabel("Property", { exact: true }).fill("pattern");
  await dialog.getByLabel("Value", { exact: true }).fill("$pattern");
  await dialog.getByRole("button", { name: "Add function" }).click();
  await expect(dialog).toBeHidden();

  await play(page);
  await page.getByRole("button", { name: "set_pattern(pattern: int)" }).click();
  await page.getByLabel("Argument pattern").fill("18");
  await page.getByRole("button", { name: "Call", exact: true }).click();
  await expect(page.locator(".call-result.ok")).toBeVisible();
  await page.screenshot({ path: "test-results/dynamic-api-call.png" });
  await expect
    .poll(async () => String((await (await request.get(`/api/projects/${id}/runtime/properties/${src.id}`)).json())
      .properties.pattern))
    .toMatch(/^(18|ball)$/);
});
