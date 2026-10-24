// Editor commands shared by toolbar, panels, shortcuts and toasts.

import { api, errorMessage } from "../api/client";
import { tapKey } from "../api/events";
import type { PropertyEvent } from "../api/events";
import type { Fix, LinkCheckResult, PropertyChange, Suggestion } from "../api/types";
import { projectGraph, useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { usePreviewStore } from "../store/previewStore";
import { notify, useUiStore, type ToastAction } from "../store/uiStore";
import { useValidationStore } from "../store/validationStore";
import { withLiveProperty } from "../lib/graphSignature";
import { ACTIVE_PAD } from "../lib/selectors";
import { useProbeStore } from "../store/probeStore";
import { isActive } from "../store/runtimeReducer";

export async function saveProject(): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  const { setSaveState } = useProjectStore.getState();
  setSaveState("saving");
  try {
    await api.updateProject(meta.id, {
      name: meta.name,
      description: meta.description,
      settings: meta.settings,
      graph: projectGraph(),
    });
    setSaveState("saved");
  } catch (error) {
    setSaveState("error", errorMessage(error));
  }
}

export async function applyFix(fix: Fix): Promise<boolean> {
  try {
    const graph = await api.applyFix(useGraphStore.getState().graph, fix);
    useGraphStore.getState().commit(graph);
    return true;
  } catch (error) {
    notify({ level: "error", title: "Could not apply the suggestion", message: errorMessage(error) });
    return false;
  }
}

export function suggestionActions(suggestions: Suggestion[], adapt: (fix: Fix) => Fix = (fix) => fix): ToastAction[] {
  return suggestions.slice(0, 4).map((suggestion) => ({
    label: suggestion.title,
    run: () => void applyFix(adapt(suggestion.fix)),
  }));
}

/** After an allowed link was added, "connect via" fixes become "insert on that edge". */
function onAddedEdge(edgeId: string) {
  return (fix: Fix): Fix =>
    fix.kind === "connect_via" ? { kind: "insert_on_edge", edge_id: edgeId, elements: fix.elements ?? [] } : fix;
}

export function reportLinkResult(result: LinkCheckResult): void {
  const messages = result.issues.map((issue) => issue.message);
  const suggestions = result.issues.flatMap((issue) => issue.suggestions);
  if (!result.allowed) {
    notify({
      level: "error",
      title: "These pads cannot be linked",
      details: messages,
      actions: suggestionActions(suggestions),
      timeout: suggestions.length ? 0 : 9000,
    });
    return;
  }
  if (result.issues.length === 0) return;
  notify({
    level: result.severity === "warning" ? "warning" : "info",
    title: result.severity === "warning" ? "Linked, but consider this" : "Linked — suggestion",
    details: messages,
    actions: suggestionActions(suggestions, onAddedEdge(result.edge.id)),
    timeout: 12000,
  });
}

export type LiveOutcome = "applied" | "deferred" | "failed";

/** Whether the element already reported ``change`` by itself since ``before`` (a fast deferred switch). */
function reportedSince(before: PropertyEvent | null, change: PropertyChange): boolean {
  const last = useRuntimeStore.getState().lastProperty;
  return last !== before && last?.origin === "runtime" && last.node_id === change.node_id &&
    last.property === change.property && (last.pad ?? null) === (change.pad ?? null);
}

/**
 * Applies a property on the running element. When a probe script takes the change over
 * (e.g. "switch at the next keyframe") the requested value stays *pending* until the
 * element reports it; otherwise the value actually in effect is stored.
 */
export async function applyLiveProperty(change: PropertyChange): Promise<LiveOutcome> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return "failed";
  const before = useRuntimeStore.getState().lastProperty;
  try {
    const result = await api.runtimeSetProperty(meta.id, change);
    if (!result.ok) {
      notify({ level: "error", title: `Live change of ${change.property} failed`, message: result.error ?? undefined });
      return "failed";
    }
    const runtime = useRuntimeStore.getState();
    const effective = result.deferred ? change.value : result.value;
    if (runtime.runningGraph) {
      const applied = effective ?? change.value;
      runtime.setRunningGraph(withLiveProperty(runtime.runningGraph, change.node_id, change.property, applied, change.pad));
    }
    if (result.deferred) {
      if (!reportedSince(before, change)) runtime.setPending(change.node_id, change.property, change.value, change.pad);
      return "deferred";
    }
    if (effective === undefined || effective === null || effective === change.value) return "applied";
    const graph = useGraphStore.getState();
    if (change.pad) graph.setPadProperty(change.node_id, change.pad, change.property, effective);
    else graph.setProperty(change.node_id, change.property, effective);
    return "applied";
  } catch (error) {
    notify({ level: "error", title: `Live change of ${change.property} failed`, message: errorMessage(error) });
    return "failed";
  }
}

/** Applies a property on the running element; false when it was refused. */
export async function sendLiveProperty(change: PropertyChange): Promise<boolean> {
  return (await applyLiveProperty(change)) !== "failed";
}

/** Makes ``pad`` the active pad of a selector: saved in the graph and, while running, applied live. */
export async function selectActivePad(nodeId: string, pad: string): Promise<void> {
  useGraphStore.getState().setProperty(nodeId, ACTIVE_PAD, pad);
  const runtime = useRuntimeStore.getState();
  if (!isActive(runtime.state)) return;
  const previous = runtime.liveProps[nodeId]?.[ACTIVE_PAD];
  runtime.setLiveProp(nodeId, ACTIVE_PAD, pad);
  const change = { node_id: nodeId, property: ACTIVE_PAD, value: pad };
  const before = useRuntimeStore.getState().lastProperty;
  const outcome = await applyLiveProperty(change);
  // Deferred: the pad is still the old one until the element reports the switch.
  if (outcome === "failed" || (outcome === "deferred" && !reportedSince(before, change))) {
    useRuntimeStore.getState().setLiveProp(nodeId, ACTIVE_PAD, previous);
  }
}

/** Starts or stops inspecting the buffers and events of a link. */
export async function setLinkProbe(edgeId: string, enabled: boolean): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  try {
    const result = await api.runtimeProbe(meta.id, edgeId, enabled);
    if (!result.ok) {
      notify({ level: "error", title: "Cannot probe this link", message: result.error ?? undefined });
      if (enabled) return;
    }
  } catch (error) {
    notify({ level: "error", title: "Cannot probe this link", message: errorMessage(error) });
    if (enabled) return;
  }
  useProbeStore.getState().setProbed(edgeId, enabled);
  if (enabled) useUiStore.getState().setDockTab("probe");
}

/** Starts or stops previewing what flows through a link. */
export async function setLinkTap(edgeId: string, enabled: boolean): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  const previews = usePreviewStore.getState();
  try {
    const result = await api.runtimeTap(meta.id, edgeId, enabled);
    if (!result.ok) {
      notify({ level: "error", title: "Cannot watch this link", message: result.error ?? undefined });
      if (enabled) return;
    }
  } catch (error) {
    notify({ level: "error", title: "Cannot watch this link", message: errorMessage(error) });
    if (enabled) return;
  }
  previews.setTapped(edgeId, enabled);
  if (enabled) useUiStore.getState().setDockTab("preview");
  else previews.remove(tapKey(edgeId));
}

export async function runPipeline(): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  const { state, setStatus } = useRuntimeStore.getState();
  if (state !== "paused" && state !== "ready") {
    await startPipeline();
    return;
  }
  try {
    setStatus(await api.runtimePlay(meta.id));
  } catch (error) {
    notify({ level: "error", title: "Could not resume the pipeline", message: errorMessage(error) });
  }
}

/** (Re)builds the pipeline from the current graph; a running one is replaced. */
export async function startPipeline(): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  const errors = useValidationStore.getState().counts.error;
  if (errors > 0 && !window.confirm(`The pipeline has ${errors} validation error(s). Run it anyway?`)) return;
  const graph = projectGraph();
  try {
    const status = await api.runtimeStart(meta.id, graph, meta.settings.gst_debug);
    useRuntimeStore.getState().setStatus(status);
    useRuntimeStore.getState().setRunningGraph(graph);
  } catch (error) {
    notify({ level: "error", title: "Could not start the pipeline", message: errorMessage(error) });
  }
}

export async function pausePipeline(): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  try {
    useRuntimeStore.getState().setStatus(await api.runtimePause(meta.id));
  } catch (error) {
    notify({ level: "error", title: "Pause failed", message: errorMessage(error) });
  }
}

export async function stopPipeline(mode: "eos" | "kill"): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  try {
    useRuntimeStore.getState().setStatus(await api.runtimeStop(meta.id, mode));
  } catch (error) {
    notify({ level: "error", title: "Stop failed", message: errorMessage(error) });
  }
}
