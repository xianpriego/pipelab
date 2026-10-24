import { useEffect } from "react";
import { api } from "../api/client";
import type { BusEvent, RuntimeEvent, ScriptEvent } from "../api/events";
import { RuntimeConnection } from "../api/runtime";
import { useGraphStore } from "../store/graphStore";
import { usePreviewStore } from "../store/previewStore";
import { useProbeStore } from "../store/probeStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { notify } from "../store/uiStore";

/** On (re)connect the server replays recent events; don't toast those again. */
const REPLAY_WINDOW_MS = 600;

function nodeName(nodeId: string | null): string | null {
  if (!nodeId) return null;
  return useGraphStore.getState().graph.nodes.find((node) => node.id === nodeId)?.name ?? null;
}

function announceError(event: BusEvent): void {
  const source = nodeName(event.node_id) ?? event.source ?? "pipeline";
  notify({
    level: "error",
    title: `Error in ${source}`,
    message: [event.text, event.hint].filter(Boolean).join("\n\n"),
    timeout: 15000,
  });
}

/** Name of a probe rule set from its runtime id ("<instance>/<probe id>" inside components). */
function probeName(probeId: string): string {
  const own = probeId.split("/").pop() ?? probeId;
  const probe = (useGraphStore.getState().graph.probes ?? []).find((p) => p.id === own);
  const instance = probeId.includes("/") ? probeId.slice(0, probeId.lastIndexOf("/")) : "";
  const name = probe?.name ?? own;
  return instance ? `${instance}/${name}` : name;
}

function announceScriptError(event: ScriptEvent): void {
  notify({ level: "error", title: `Script "${event.name}" failed`, message: event.message, timeout: 15000 });
}

function sideEffects(event: RuntimeEvent, replaying: boolean): void {
  if (event.type === "bus" && event.kind === "error" && !replaying) announceError(event);
  if (event.type === "probe") useProbeStore.getState().ingest(event);
  if (event.type === "script") {
    useProbeStore.getState().ingestScript(event);
    if (event.level === "error" && !replaying) announceScriptError(event);
  }
  if (event.type === "probe-log") useProbeStore.getState().ingestProbeLog(event, probeName(event.probe));
  if (event.type === "state" && event.state === "starting") {
    usePreviewStore.getState().clear();
    useProbeStore.getState().reset();
  }
  // Taps and probes die with the run; the last frames and probed rows stay visible.
  if (event.type === "state" && (event.state === "stopped" || event.state === "error")) {
    usePreviewStore.setState({ taps: [] });
    useProbeStore.getState().endRun();
  }
}

/** Keeps a websocket to the project's runtime and feeds the runtime/preview stores. */
export function useRuntimeConnection(projectId: string | undefined): void {
  useEffect(() => {
    if (!projectId) return undefined;
    const runtime = useRuntimeStore.getState();
    runtime.reset();
    usePreviewStore.getState().clear();
    useProbeStore.getState().reset();
    api.runtimeStatus(projectId).then(runtime.setStatus).catch(() => undefined);
    let connectedAt = 0;
    const connection = new RuntimeConnection(api.runtimeSocketUrl(projectId), {
      onEvent: (event) => {
        useRuntimeStore.getState().apply(event);
        sideEffects(event, performance.now() - connectedAt < REPLAY_WINDOW_MS);
      },
      onFrame: (frame) => usePreviewStore.getState().handleFrame(frame),
      onConnection: (connected) => {
        if (connected) {
          connectedAt = performance.now();
          useRuntimeStore.getState().clearReplayed();
          useProbeStore.getState().clearScripts();
          api.runtimeInstances(projectId)
            .then((result) => useRuntimeStore.getState().setInstances(result.slots))
            .catch(() => undefined);
        }
        useRuntimeStore.getState().setConnected(connected);
      },
    });
    connection.open();
    return () => {
      connection.close();
      usePreviewStore.getState().clear();
    };
  }, [projectId]);
}
