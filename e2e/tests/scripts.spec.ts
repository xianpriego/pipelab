import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { cleanup, createProject, node, openEditor, waitForCatalog, type Graph } from "./helpers";

// Slots, API functions, probe rules and scripts are hidden unless the web image is built with
// VITE_PIPELAB_ADVANCED=1; run these tests against such a build with ADVANCED_UI=1.
const advanced = process.env.ADVANCED_UI === "1";

test.afterEach(async ({ request }) => cleanup(request));

// 10 s GOPs: without the upstream keyframe request the switch visibly waits for the next key unit.
const SELECTOR =
  "input-selector name=sel ! fakesink " +
  "videotestsrc is-live=true ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_0 " +
  "videotestsrc is-live=true pattern=ball ! x264enc tune=zerolatency key-int-max=300 ! sel.sink_1";

async function importProject(request: APIRequestContext, name: string, description: string) {
  await waitForCatalog(request);
  const imported = await request.post("/api/import/gst-launch", { data: { description } });
  expect(imported.ok()).toBeTruthy();
  const graph = (await imported.json()).graph as Graph;
  return { id: await createProject(request, { name, graph }), graph };
}

/** Replaces the whole line containing ``text`` in the CodeMirror editor of the open dialog. */
async function replaceLine(page: Page, text: string, replacement: string) {
  await page.locator(".cm-line", { hasText: text }).first().click();
  await page.keyboard.press("Home");
  await page.keyboard.press("Shift+End");
  await page.keyboard.type(replacement);
}

test("an input-selector switches on the next keyframe through a probe script", async ({ page, request }) => {
  test.skip(!advanced, "advanced UI disabled");
  page.on("dialog", (dialog) => void dialog.accept());
  const { id, graph } = await importProject(request, "E2E keyframe switch", SELECTOR);
  const selector = graph.nodes.find((n) => n.factory === "input-selector")!;
  await openEditor(page, id);
  await node(page, "sel").click();
  await page.getByRole("button", { name: "Add the switch on keyframe script" }).click();
  await expect(node(page, "sel").locator(".script-badge")).toBeVisible();

  // Keep the switch waiting for the natural keyframe so the pending state can be observed.
  await page.getByRole("button", { name: "Edit Switch on keyframe" }).click();
  await replaceLine(page, "REQUEST_KEYFRAME = True", "REQUEST_KEYFRAME = False");
  await page.getByRole("dialog").getByRole("button", { name: "Save" }).click();

  await page.getByRole("button", { name: "Play" }).click();
  await expect(page.locator(".state-pill")).toHaveText(/playing/);
  const sink0 = page.getByRole("radio", { name: "Make sink_0 the active pad" });
  const sink1 = page.getByRole("radio", { name: "Make sink_1 the active pad" });
  await expect(sink0).toHaveAttribute("aria-checked", "true");

  await sink1.click();
  await expect(sink1).toHaveAttribute("aria-busy", "true");
  await expect(page.locator(".prop-pending")).toBeVisible();
  await page.screenshot({ path: "test-results/scripts-pending.png" });

  await expect
    .poll(async () => (await (await request.get(`/api/projects/${id}/runtime/properties/${selector.id}`)).json())
      .properties["active-pad"], { timeout: 20_000 })
    .toBe("sink_1");
  await expect(sink1).toHaveAttribute("aria-checked", "true");
  await expect(sink1).not.toHaveAttribute("aria-busy", "true");

  await page.getByRole("tab", { name: /probe/i }).click();
  await expect(page.locator("tr.probe-row.log", { hasText: /keyframe/ }).first()).toBeVisible();
  await page.screenshot({ path: "test-results/scripts-switched.png" });
});

test("a script with a syntax error shows the validation issue in its editor", async ({ page, request }) => {
  test.skip(!advanced, "advanced UI disabled");
  const { id } = await importProject(request, "E2E script error", "videotestsrc ! fakesink name=out");
  await openEditor(page, id);
  await node(page, "out").click();
  await page.getByRole("button", { name: /add script/i }).click();
  await page.getByRole("button", { name: /Blank script/ }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.locator(".cm-content")).toBeVisible();
  await replaceLine(page, "def setup(ctx):", "def setup(ctx:");
  await page.keyboard.press("Control+s");
  await expect(dialog.locator(".script-issues")).toContainText(/line \d+/i, { timeout: 15_000 });
  await expect(dialog.locator(".cm-error-line")).toHaveCount(1);
  await page.screenshot({ path: "test-results/scripts-error.png" });
});
