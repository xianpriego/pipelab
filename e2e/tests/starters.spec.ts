import { readFileSync } from "node:fs";
import { expect, test } from "@playwright/test";
import { cleanup, createProject, openEditor } from "./helpers";

test.afterEach(async ({ request }) => {
  await cleanup(request);
  await request.delete("/api/components/h264-encoder");
});

test("adds a starter component, uses it, exports it to a file and imports it back", async ({ page, request }) => {
  page.on("dialog", (dialog) => void dialog.accept());
  await request.delete("/api/components/h264-encoder");
  const id = await createProject(request, { name: "E2E starters", template: "video-test" });
  await openEditor(page, id);

  await page.getByRole("button", { name: "Starters…" }).click();
  const dialog = page.getByRole("dialog", { name: "Starter components" });
  await expect(dialog.getByText("RTSP H.264 input (NVIDIA)")).toBeVisible();
  await dialog.getByRole("button", { name: "Add H.264 encoder", exact: true }).click();
  await expect(dialog.getByRole("button", { name: "Add H.264 encoder", exact: true })).toHaveText("In the library");
  await page.screenshot({ path: "test-results/starters.png" });
  await dialog.getByRole("button", { name: "Close", exact: true }).last().click();

  // It is in the palette like any element: add it and open it.
  await page.getByPlaceholder(/Search/).fill("H.264 encoder");
  await page.locator(".palette-item", { hasText: "component:h264-encoder" }).first().dblclick();
  const instance = page.locator(".react-flow__node").filter({ has: page.locator(".component-glyph") });
  await expect(instance).toHaveCount(1);
  await instance.dblclick();
  await expect(page.getByRole("navigation", { name: "Component breadcrumbs" })).toContainText("H.264 encoder");

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export to file" }).click();
  const file = await (await download).path();
  expect(JSON.parse(readFileSync(file, "utf8")).components[0].id).toBe("h264-encoder");

  await page.getByRole("button", { name: "Delete component" }).click();
  await expect(page.getByRole("navigation", { name: "Component breadcrumbs" })).toBeHidden();
  await expect.poll(async () => (await request.get("/api/components/h264-encoder")).status()).toBe(404);

  // The palette actions are shown when not searching.
  await page.getByPlaceholder(/Search/).fill("");
  await page.getByLabel("Component file").setInputFiles(file);
  await expect(page.getByText("Imported h264-encoder")).toBeVisible();
  expect((await request.get("/api/components/h264-encoder")).status()).toBe(200);
});
