import { expect, type APIRequestContext, type Page } from "@playwright/test";

export interface Graph {
  nodes: {
    id: string;
    factory: string;
    name: string;
    properties?: Record<string, unknown>;
    position?: { x: number; y: number };
  }[];
  edges: { id: string; source: string; source_pad: string; target: string; target_pad: string }[];
}

const created: string[] = [];

export async function waitForCatalog(request: APIRequestContext): Promise<void> {
  await expect
    .poll(async () => (await (await request.get("/api/health")).json()).catalog.state, { timeout: 60_000 })
    .toBe("ready");
}

export async function createProject(
  request: APIRequestContext,
  body: { name: string; template?: string; graph?: Graph },
): Promise<string> {
  await waitForCatalog(request);
  const response = await request.post("/api/projects", { data: body });
  expect(response.ok()).toBeTruthy();
  const project = await response.json();
  created.push(project.id);
  return project.id;
}

export function track(projectId: string): void {
  created.push(projectId);
}

export async function cleanup(request: APIRequestContext): Promise<void> {
  while (created.length) {
    const id = created.pop()!;
    await request.post(`/api/projects/${id}/runtime/stop`, { data: { mode: "kill" } });
    await request.delete(`/api/projects/${id}`);
  }
}

export async function openEditor(page: Page, projectId: string): Promise<void> {
  await page.goto(`/projects/${projectId}`);
  await expect(page.locator(".react-flow__node").first()).toBeVisible();
}

export function node(page: Page, name: string) {
  return page.locator(".react-flow__node").filter({ hasText: name }).first();
}

/** Drag a connection between two pad handles of two nodes. */
export async function connect(page: Page, fromNode: string, fromPad: string, toNode: string, toPad: string) {
  const source = node(page, fromNode).locator(`.react-flow__handle[data-handleid="${fromPad}"]`);
  const target = node(page, toNode).locator(`.react-flow__handle[data-handleid="${toPad}"]`);
  const a = (await source.boundingBox())!;
  const b = (await target.boundingBox())!;
  await page.mouse.move(a.x + a.width / 2, a.y + a.height / 2);
  await page.mouse.down();
  await page.mouse.move((a.x + b.x) / 2, (a.y + b.y) / 2, { steps: 8 });
  await page.mouse.move(b.x + b.width / 2, b.y + b.height / 2, { steps: 8 });
  await page.mouse.up();
}
