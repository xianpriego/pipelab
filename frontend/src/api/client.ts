// Typed HTTP client of the Pipelab API.

import type { ComponentBundle, ComponentDef, ComponentUsage, GroupResult, StarterInfo } from "./components";
import type {
  ElementInfo, ElementSummary, ExportFormat, ExportResult, Fix, Graph, GraphEdge, Health,
  ImportResult, Issue, LinkCheckResult, LiveProperties, MediaFile, MonitorPipeline, MonitorProcess,
  Project, ProjectCreate, ProbeResult, ProjectSummary, ProjectUpdate, PropertyChange, PropertyResult,
  RuntimeStatus, TapResult, TemplateInfo,
} from "./types";

export const API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function describeDetail(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (typeof item === "object" && item !== null && "msg" in item) {
          const loc = Array.isArray((item as { loc?: unknown[] }).loc)
            ? (item as { loc: unknown[] }).loc.join(".")
            : "";
          return loc ? `${loc}: ${String((item as { msg: unknown }).msg)}` : String((item as { msg: unknown }).msg);
        }
        return String(item);
      })
      .join("; ");
  }
  return null;
}

export async function errorFromResponse(response: Response): Promise<ApiError> {
  let message = `${response.status} ${response.statusText}`.trim();
  try {
    const body: unknown = await response.json();
    const detail = typeof body === "object" && body !== null ? describeDetail((body as { detail?: unknown }).detail) : null;
    if (detail) message = detail;
  } catch {
    // Non JSON error body: keep the status line.
  }
  return new ApiError(response.status, message);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, { ...init, headers });
  } catch (error) {
    throw new ApiError(0, `Cannot reach the Pipelab API (${(error as Error).message})`);
  }
  if (!response.ok) throw await errorFromResponse(response);
  if (response.status === 204) return undefined as T;
  const type = response.headers.get("Content-Type") ?? "";
  return (type.includes("application/json") ? response.json() : response.text()) as Promise<T>;
}

const json = (body: unknown): RequestInit => ({ method: "POST", body: JSON.stringify(body) });
const enc = encodeURIComponent;
const runtime = (id: string) => `/projects/${enc(id)}/runtime`;

export const api = {
  health: () => request<Health>("/health"),
  catalog: async () => (await request<{ elements: ElementSummary[] }>("/catalog")).elements,
  element: (factory: string) => request<ElementInfo>(`/catalog/${enc(factory)}`),

  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (body: ProjectCreate) => request<Project>("/projects", json(body)),
  getProject: (id: string) => request<Project>(`/projects/${enc(id)}`),
  updateProject: (id: string, body: ProjectUpdate) =>
    request<Project>(`/projects/${enc(id)}`, { method: "PUT", body: JSON.stringify(body) }),
  deleteProject: (id: string) => request<void>(`/projects/${enc(id)}`, { method: "DELETE" }),
  duplicateProject: (id: string) => request<Project>(`/projects/${enc(id)}/duplicate`, { method: "POST" }),
  templates: () => request<TemplateInfo[]>("/templates"),

  checkLink: (graph: Graph, edge: GraphEdge) => request<LinkCheckResult>("/graph/check-link", json({ graph, edge })),
  validate: async (graph: Graph) => (await request<{ issues: Issue[] }>("/graph/validate", json({ graph }))).issues,
  applyFix: async (graph: Graph, fix: Fix) => (await request<{ graph: Graph }>("/graph/apply-fix", json({ graph, fix }))).graph,
  layout: async (graph: Graph) => (await request<{ graph: Graph }>("/graph/layout", json({ graph }))).graph,

  exportFormats: () => request<ExportFormat[]>("/export/formats"),
  exportGraph: (graph: Graph, format: string, name: string) =>
    request<ExportResult>("/export", json({ graph, format, name })),
  importGstLaunch: (description: string) => request<ImportResult>("/import/gst-launch", json({ description })),

  runtimeStatus: (id: string) => request<RuntimeStatus>(`${runtime(id)}/status`),
  runtimeStart: (id: string, graph: Graph, gstDebug?: string) =>
    request<RuntimeStatus>(`${runtime(id)}/start`, json({ graph, gst_debug: gstDebug ?? null })),
  runtimePlay: (id: string) => request<RuntimeStatus>(`${runtime(id)}/play`, { method: "POST" }),
  runtimePause: (id: string) => request<RuntimeStatus>(`${runtime(id)}/pause`, { method: "POST" }),
  runtimeStop: (id: string, mode: "eos" | "kill") => request<RuntimeStatus>(`${runtime(id)}/stop`, json({ mode })),
  runtimeSetProperty: (id: string, change: PropertyChange) =>
    request<PropertyResult>(`${runtime(id)}/property`, json(change)),
  runtimeTap: (id: string, edgeId: string, enabled: boolean) =>
    request<TapResult>(`${runtime(id)}/tap`, json({ edge_id: edgeId, enabled })),
  runtimeProbe: (id: string, edgeId: string, enabled: boolean) =>
    request<ProbeResult>(`${runtime(id)}/probe`, json({ edge_id: edgeId, enabled })),
  runtimeProperties: (id: string, nodeId: string) =>
    request<LiveProperties>(`${runtime(id)}/properties/${enc(nodeId)}`),
  runtimeDotUrl: (id: string) => `${API_BASE}${runtime(id)}/dot?t=${Date.now()}`,
  runtimeSocketUrl: (id: string, location: Pick<Location, "protocol" | "host"> = window.location) =>
    `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}${API_BASE}${runtime(id)}/ws`,

  listComponents: () => request<ComponentDef[]>("/components"),
  getComponent: (id: string) => request<ComponentDef>(`/components/${enc(id)}`),
  saveComponent: (component: ComponentDef) =>
    request<ComponentDef>(`/components/${enc(component.id)}`, { method: "PUT", body: JSON.stringify(component) }),
  deleteComponent: (id: string) => request<void>(`/components/${enc(id)}`, { method: "DELETE" }),
  listStarters: () => request<StarterInfo[]>("/components/starters"),
  installStarter: (id: string) => request<ComponentDef>(`/components/starters/${enc(id)}`, { method: "POST" }),
  componentBundle: (id: string) => request<ComponentBundle>(`/components/${enc(id)}/bundle`),
  /** 409 when some ids are already in the library, unless ``overwrite``. */
  importComponents: (bundle: ComponentBundle, overwrite = false) =>
    request<{ imported: string[] }>("/components/import", json({ bundle, overwrite })),
  /** Components and projects that break when ``id`` is deleted. */
  componentUsage: (id: string) => request<ComponentUsage>(`/components/${enc(id)}/usage`),
  /** Validates a definition: no source/sink checks, exposed ports may stay unlinked. */
  validateComponent: async (component: ComponentDef) =>
    (await request<{ issues: Issue[] }>("/components/validate", json({ component }))).issues,
  groupIntoComponent: (graph: Graph, nodeIds: string[], id: string, name: string) =>
    request<GroupResult>("/components/from-selection", json({ graph, node_ids: nodeIds, id, name })),
  expandInstance: async (graph: Graph, nodeId: string) =>
    (await request<{ graph: Graph }>("/graph/expand", json({ graph, node_id: nodeId }))).graph,

  listMedia: async () => (await request<{ files: MediaFile[] }>("/media")).files,
  uploadMedia: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<MediaFile>("/media", { method: "POST", body });
  },
  deleteMedia: (path: string) => request<void>(`/media/${path.split("/").map(enc).join("/")}`, { method: "DELETE" }),
  mediaUrl: (path: string) => `${API_BASE}/media/${path.split("/").map(enc).join("/")}`,

  monitorProcesses: async () =>
    (await request<{ processes: MonitorProcess[] }>("/monitor/processes")).processes,
  monitorSnapshot: (pid: number, method: "auto" | "gdb" | "dot-dir" = "auto") =>
    request<MonitorPipeline>("/monitor/snapshot", json({ pid, method })),
};

export function errorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  return String(error);
}
