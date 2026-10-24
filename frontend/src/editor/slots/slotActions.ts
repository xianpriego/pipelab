// Commands on slots: create them next to mixers/selectors/tees, and manage live instances.

import { api, errorMessage } from "../../api/client";
import type { CallResult, Slot, SlotLink, Value } from "../../api/dynamic";
import type { ElementSummary, GraphNode, Position } from "../../api/types";
import { COMPONENT_PREFIX } from "../../lib/components";
import { createSlot } from "../../lib/slots";
import { useCatalogStore } from "../../store/catalogStore";
import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { useRuntimeStore } from "../../store/runtimeStore";
import { notify, useUiStore } from "../../store/uiStore";
import { slotNodeId } from "./slotFlow";

/** Request pad template of ``direction`` on an element (compositor sink_%u, tee src_%u…). */
export function requestTemplate(summary: ElementSummary | undefined, direction: "sink" | "src"): string | undefined {
  return summary?.pads.find((pad) => pad.direction === direction && pad.presence === "request")?.name;
}

/** Elements instances can be attached to: anything with request pads. */
export function acceptsSlots(summary: ElementSummary | undefined): boolean {
  return Boolean(requestTemplate(summary, "sink") || requestTemplate(summary, "src"));
}

/**
 * First link of a new slot on ``node``: a component output feeds a request sink pad (compositor,
 * audiomixer, input-selector), or a request src pad (tee) feeds a component input.
 */
export function defaultLink(node: GraphNode, nodeSummary: ElementSummary | undefined, componentSummary: ElementSummary | undefined): SlotLink | null {
  const ports = componentSummary?.pads ?? [];
  const sinkPad = requestTemplate(nodeSummary, "sink");
  const output = ports.find((port) => port.direction === "src");
  if (sinkPad && output) return { port: output.name, node_id: node.id, pad: sinkPad, pad_properties: {} };
  const srcPad = requestTemplate(nodeSummary, "src");
  const input = ports.find((port) => port.direction === "sink");
  if (srcPad && input) return { port: input.name, node_id: node.id, pad: srcPad, pad_properties: {} };
  return null;
}

/** Adds a slot of ``component`` linked to ``nodeId`` and selects it. */
export function addSlotOn(nodeId: string, component: string): Slot {
  const { byName } = useCatalogStore.getState();
  const node = useGraphStore.getState().graph.nodes.find((n) => n.id === nodeId);
  const link = node ? defaultLink(node, byName[node.factory], byName[`${COMPONENT_PREFIX}${component}`]) : null;
  const slot = createSlot(component, link ? [link] : []);
  useGraphStore.getState().addSlot(slot);
  useUiStore.getState().select([slotNodeId(slot.id)], []);
  useUiStore.getState().requestFit();
  return slot;
}

/** Adds an unlinked slot where a component was dropped (Alt-drag from the palette). */
export function addSlotAt(component: string, position: Position): Slot {
  const slot = { ...createSlot(component), position };
  useGraphStore.getState().addSlot(slot);
  useUiStore.getState().select([slotNodeId(slot.id)], []);
  return slot;
}

export async function refreshInstances(): Promise<void> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return;
  try {
    useRuntimeStore.getState().setInstances((await api.runtimeInstances(meta.id)).slots);
  } catch {
    // Not running (or an older runtime): the "instances" events keep the list up to date.
  }
}

/** Calls a pipeline API function on the running pipeline. */
export async function callFunction(name: string, args: Record<string, Value>): Promise<CallResult> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return { ok: false, error: "No project open" };
  try {
    return await api.runtimeCall(meta.id, name, args);
  } catch (error) {
    return { ok: false, error: errorMessage(error) };
  }
}

async function slotCall(title: string, name: string, args: Record<string, Value>): Promise<CallResult> {
  const result = await callFunction(name, args);
  if (!result.ok) notify({ level: "error", title, message: result.error ?? undefined });
  void refreshInstances();
  return result;
}

export function addLiveInstance(slot: Slot, params: Record<string, Value>): Promise<CallResult> {
  return slotCall(`Could not add ${slot.item}`, `add_${slot.item}`, params);
}

export function removeLiveInstance(slot: Slot, id: string): Promise<CallResult> {
  return slotCall(`Could not remove ${id}`, `remove_${slot.item}`, { id });
}

export function restartLiveInstance(slot: Slot, id: string): Promise<CallResult> {
  return slotCall(`Could not restart ${id}`, `restart_${slot.item}`, { id });
}
