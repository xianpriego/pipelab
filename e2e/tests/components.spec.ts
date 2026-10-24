import { expect, test, type APIRequestContext } from "@playwright/test";
import { cleanup, createProject, node, openEditor, waitForCatalog, type Graph } from "./helpers";

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
  await page.screenshot({ path: "test-results/components-grouped.png" });

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
  await page.screenshot({ path: "test-results/components-inside.png" });

  await crumbs.getByRole("button", { name: "E2E group", exact: true }).click();
  await expect(crumbs).toBeHidden();
  await expect(page.locator(".react-flow__node")).toHaveCount(3);
  await expect(instance).toHaveCount(1);
});
