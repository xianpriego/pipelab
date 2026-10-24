// Slots: N instances of a component linked to the static graph (docs/DYNAMIC.md §2).

import type { ComponentDef, FunctionParam, ParamType, Slot, SlotInstance, Value } from "../api/dynamic";
import type { ElementSummary, Graph, PropertyInfo } from "../api/types";
import { newId } from "./ids";

export function slotsOf(graph: Graph): Slot[] {
  return graph.slots ?? [];
}

export function addSlot(graph: Graph, slot: Slot): Graph {
  return { ...graph, slots: [...slotsOf(graph), slot] };
}

export function updateSlot(graph: Graph, id: string, patch: Partial<Omit<Slot, "id">>): Graph {
  return { ...graph, slots: slotsOf(graph).map((slot) => (slot.id === id ? { ...slot, ...patch } : slot)) };
}

export function removeSlot(graph: Graph, id: string): Graph {
  return { ...graph, slots: slotsOf(graph).filter((slot) => slot.id !== id) };
}

/** "rtsp-input" → item "rtsp_input", name "rtsp_inputs". */
export function slotNames(componentId: string): { item: string; name: string } {
  const item = componentId.replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "").toLowerCase() || "instance";
  return { item, name: item.endsWith("s") ? `${item}es` : `${item}s` };
}

export function createSlot(component: string, links: Slot["links"] = []): Slot {
  const { item, name } = slotNames(component);
  return { id: newId("slot"), name, item, component, links, initial: [], max_instances: null };
}

/** ``<item><n>`` with the smallest free n. */
export function nextInstanceId(item: string, taken: string[]): string {
  const used = new Set(taken);
  for (let n = 0; ; n += 1) {
    if (!used.has(`${item}${n}`)) return `${item}${n}`;
  }
}

export function addInitialInstance(slot: Slot, params: Record<string, Value> = {}): Slot {
  const id = nextInstanceId(slot.item, slot.initial.map((instance) => instance.id));
  return { ...slot, initial: [...slot.initial, { id, params }] };
}

/** Slots whose links point at elements that no longer exist (left for validation to report). */
export function brokenSlotLinks(graph: Graph): string[] {
  const nodes = new Set(graph.nodes.map((node) => node.id));
  return slotsOf(graph).filter((slot) => slot.links.some((link) => !nodes.has(link.node_id))).map((slot) => slot.id);
}

/** Parameter type of a component property (from its virtual element). */
export function paramType(prop: PropertyInfo | undefined): ParamType {
  if (!prop) return "string";
  if (prop.type === "boolean") return "bool";
  if (prop.type === "float" || prop.type === "double") return "float";
  if (["int", "uint", "int64", "uint64"].includes(prop.type)) return "int";
  return "string";
}

/** Signature of a built-in slot function, for the API panel. */
export interface BuiltinFunction {
  name: string;
  params: FunctionParam[];
  returns: string;
  description: string;
  slot: string;
}

export function builtinFunctions(slot: Slot, componentParams: PropertyInfo[]): BuiltinFunction[] {
  const params: FunctionParam[] = componentParams
    .filter((prop) => prop.writable)
    .map((prop) => ({ name: prop.name, type: paramType(prop), default: prop.default, description: prop.blurb }));
  const id: FunctionParam[] = [{ name: "id", type: "string", description: `instance id (e.g. ${slot.item}0)` }];
  // add_<item> takes an optional id (generated when omitted).
  const optionalId: FunctionParam = { ...id[0], default: null, description: "optional instance id" };
  return [
    { name: `add_${slot.item}`, params: [...params, optionalId], returns: "id", description: `Adds an instance of ${slot.component}`, slot: slot.id },
    { name: `remove_${slot.item}`, params: id, returns: "", description: "Removes an instance while running", slot: slot.id },
    { name: `restart_${slot.item}`, params: id, returns: "", description: "Removes and re-adds it with the same parameters", slot: slot.id },
    { name: `list_${slot.name}`, params: [], returns: "[{id, params}]", description: "Live instances", slot: slot.id },
  ];
}

/** Live instances when running, else the configured initial ones. */
export function shownInstances(slot: Slot, live: Record<string, SlotInstance[]>, running: boolean): SlotInstance[] {
  return running && live[slot.id] ? live[slot.id] : slot.initial;
}

export function componentOfSlot(slot: Slot, library: ComponentDef[]): ComponentDef | undefined {
  return library.find((component) => component.id === slot.component);
}

export function componentSummary(slot: Slot, byName: Record<string, ElementSummary>): ElementSummary | undefined {
  return byName[`component:${slot.component}`];
}

/** The stored position, else beside the first linked element (right of it for consumers), stacked per slot. */
export function slotPosition(slot: Slot, graph: Graph, index: number, consumer = false): { x: number; y: number } {
  if (slot.position) return slot.position;
  const target = graph.nodes.find((node) => node.id === slot.links[0]?.node_id);
  const base = target?.position ?? { x: 0, y: 0 };
  return { x: base.x + (consumer ? 300 : -300), y: base.y + index * 170 };
}

/** Whether a component port receives data from the static graph. */
export function isSinkPort(port: string, ports: { name: string; direction: string }[]): boolean {
  return ports.find((p) => p.name === port)?.direction === "sink";
}
