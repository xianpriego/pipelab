// Components (macro blocks): pure helpers on definitions, ports and parameters.

import type { ComponentDef, ComponentParam, ComponentPort, ParamTarget, Value } from "../api/dynamic";
import type { Graph, Issue } from "../api/types";

export const COMPONENT_PREFIX = "component:";

export function isComponentFactory(factory: string): boolean {
  return factory.startsWith(COMPONENT_PREFIX);
}

export function componentIdOf(factory: string): string | null {
  return isComponentFactory(factory) ? factory.slice(COMPONENT_PREFIX.length) : null;
}

/** "RTSP input #1" → "rtsp-input-1". */
export function slugify(name: string): string {
  return name.toLowerCase().normalize("NFKD").replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

export function emptyComponent(id: string, name: string, graph: Graph = { nodes: [], edges: [] }): ComponentDef {
  return { id, name, description: "", version: 0, graph, ports: [], parameters: [] };
}

// --- Ports ------------------------------------------------------------------------

/** Exposed pads of an inner node: pad → port name. */
export function portsOfNode(ports: ComponentPort[], nodeId: string): Record<string, string> {
  return Object.fromEntries(ports.filter((p) => p.node_id === nodeId).map((p) => [p.pad, p.name]));
}

/** Port names must be unique; a pad is exposed at most once. */
export function exposePort(ports: ComponentPort[], port: ComponentPort): ComponentPort[] {
  const others = ports.filter(
    (p) => p.name !== port.name && !(p.node_id === port.node_id && p.pad === port.pad),
  );
  return [...others, port];
}

export function renamePort(ports: ComponentPort[], from: string, to: string): ComponentPort[] | null {
  if (!to || (to !== from && ports.some((p) => p.name === to))) return null;
  return ports.map((p) => (p.name === from ? { ...p, name: to } : p));
}

export function removePort(ports: ComponentPort[], name: string): ComponentPort[] {
  return ports.filter((p) => p.name !== name);
}

/** "sink_%u" → "sink", "video_0" → "video_0". */
export function suggestPortName(pad: string, taken: string[]): string {
  const base = pad.replace(/_?%[uds]/g, "") || "pad";
  let name = base;
  for (let i = 1; taken.includes(name); i += 1) name = `${base}_${i}`;
  return name;
}

// --- Parameters -----------------------------------------------------------------

/** Adds a target to the parameter ``name`` (created when missing). */
export function exposeParam(
  params: ComponentParam[], name: string, target: ParamTarget, description = "", defaultValue: Value = null,
): ComponentParam[] {
  const existing = params.find((p) => p.name === name);
  if (!existing) return [...params, { name, description, default: defaultValue, targets: [target] }];
  const known = existing.targets.some(
    (t) => t.node_id === target.node_id && t.property === target.property && (t.pad ?? null) === (target.pad ?? null),
  );
  return params.map((p) => (p.name === name && !known ? { ...p, targets: [...p.targets, target] } : p));
}

export function updateParam(params: ComponentParam[], name: string, patch: Partial<ComponentParam>): ComponentParam[] | null {
  if (patch.name && patch.name !== name && params.some((p) => p.name === patch.name)) return null;
  return params.map((p) => (p.name === name ? { ...p, ...patch } : p));
}

export function removeParam(params: ComponentParam[], name: string): ComponentParam[] {
  return params.filter((p) => p.name !== name);
}

export function removeParamTarget(params: ComponentParam[], name: string, index: number): ComponentParam[] {
  return params.map((p) => (p.name === name ? { ...p, targets: p.targets.filter((_t, i) => i !== index) } : p));
}

/** Parameter driving an inner (pad) property, if any. */
export function paramOf(params: ComponentParam[], nodeId: string, property: string, pad?: string | null): string | undefined {
  return params.find((p) =>
    p.targets.some((t) => t.node_id === nodeId && t.property === property && (t.pad ?? null) === (pad ?? null)),
  )?.name;
}

/** Ports and parameter targets pointing at nodes that no longer exist are dropped. */
export function pruneDefinition(def: ComponentDef, graph: Graph): Pick<ComponentDef, "ports" | "parameters"> {
  const nodes = new Set(graph.nodes.map((node) => node.id));
  return {
    ports: def.ports.filter((p) => nodes.has(p.node_id)),
    parameters: def.parameters.map((p) => ({ ...p, targets: p.targets.filter((t) => nodes.has(t.node_id)) })),
  };
}

/**
 * Validation issues of ``rule`` about an entity: the issue id mentions its id, or the message
 * names it (e.g. "Slot 'inputs': …").
 */
export function issuesAbout(issues: Issue[], rule: string, id: string, name?: string): Issue[] {
  return issues.filter((issue) => {
    if (issue.rule !== rule) return false;
    if (issue.id.split(":").includes(id)) return true;
    return name !== undefined && issue.message.includes(`'${name}'`);
  });
}
