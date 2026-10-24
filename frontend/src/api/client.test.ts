import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./client";

function respond(status: number, body: unknown, contentType = "application/json") {
  return vi.fn().mockResolvedValue(
    new Response(typeof body === "string" ? body : JSON.stringify(body), {
      status,
      headers: { "Content-Type": contentType },
    }),
  );
}

describe("api client", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("returns parsed JSON and sends JSON bodies", async () => {
    const fetchMock = respond(200, { issues: [] });
    vi.stubGlobal("fetch", fetchMock);
    await expect(api.validate({ nodes: [], edges: [] })).resolves.toEqual([]);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/graph/validate");
    expect(init.method).toBe("POST");
    expect(new Headers(init.headers).get("Content-Type")).toBe("application/json");
    expect(JSON.parse(init.body)).toEqual({ graph: { nodes: [], edges: [] } });
  });

  it("surfaces the backend detail message", async () => {
    vi.stubGlobal("fetch", respond(404, { detail: "Project not found" }));
    await expect(api.getProject("x")).rejects.toEqual(new ApiError(404, "Project not found"));
  });

  it("flattens validation errors", async () => {
    vi.stubGlobal("fetch", respond(422, { detail: [{ loc: ["body", "name"], msg: "Field required" }] }));
    await expect(api.createProject({ name: "" })).rejects.toThrow("body.name: Field required");
  });

  it("falls back to the status line for non JSON errors", async () => {
    vi.stubGlobal("fetch", respond(502, "<html>bad gateway</html>", "text/html"));
    const error = await api.health().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(502);
  });

  it("reports network failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    await expect(api.listProjects()).rejects.toThrow("Cannot reach the Pipelab API");
  });

  it("builds websocket and media URLs", () => {
    expect(api.runtimeSocketUrl("p1", { protocol: "https:", host: "example.com" })).toBe(
      "wss://example.com/api/projects/p1/runtime/ws",
    );
    expect(api.mediaUrl("out dir/a b.mp4")).toBe("/api/media/out%20dir/a%20b.mp4");
  });
});
