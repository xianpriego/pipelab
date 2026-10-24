// Pad handles of a node: always pads, request pads (+ "new pad" handle) and sometimes pads.

import type { GraphEdge, GraphNode, PadDirection, PadPresence, PadSummary } from "../api/types";

export type HandleKind = "always" | "request" | "request-new" | "sometimes" | "orphan";

export interface HandleSpec {
  id: string;
  label: string;
  direction: PadDirection;
  presence: PadPresence | "unknown";
  kind: HandleKind;
  mediaTypes: string[];
  template: string;
}

export interface NodeHandles {
  sinks: HandleSpec[];
  srcs: HandleSpec[];
}

const TOKENS: Record<string, string> = { "%u": "\\d+", "%d": "-?\\d+", "%s": ".+" };
const regexCache = new Map<string, RegExp>();

export function templateRegex(template: string): RegExp {
  let regex = regexCache.get(template);
  if (!regex) {
    const escaped = template.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    regex = new RegExp(`^${escaped.replace(/%[uds]/g, (token) => TOKENS[token])}$`);
    regexCache.set(template, regex);
  }
  return regex;
}

/** Template a concrete (`sink_3`) or template (`sink_%u`) pad name belongs to. */
export function findTemplate<T extends PadSummary>(pads: T[], padName: string): T | undefined {
  return (
    pads.find((pad) => pad.name === padName) ??
    pads.find((pad) => pad.presence !== "always" && templateRegex(pad.name).test(padName))
  );
}

function padIndex(name: string): number {
  const match = /(\d+)(?!.*\d)/.exec(name);
  return match ? Number(match[1]) : 0;
}

export function usedPads(nodeId: string, edges: GraphEdge[], direction: PadDirection): string[] {
  const names = edges
    .filter((edge) => (direction === "src" ? edge.source === nodeId : edge.target === nodeId))
    .map((edge) => (direction === "src" ? edge.source_pad : edge.target_pad));
  return [...new Set(names)];
}

function handlesFor(pads: PadSummary[], used: string[], direction: PadDirection): HandleSpec[] {
  const handles: HandleSpec[] = [];
  const claimed = new Set<string>();
  const make = (id: string, pad: PadSummary, kind: HandleKind, label = id): HandleSpec => ({
    id, label, direction, presence: pad.presence, kind, mediaTypes: pad.media_types, template: pad.name,
  });
  for (const pad of pads.filter((p) => p.direction === direction)) {
    const concrete = used
      .filter((name) => name !== pad.name && pad.presence !== "always" && templateRegex(pad.name).test(name))
      .filter((name) => !claimed.has(name))
      .sort((a, b) => padIndex(a) - padIndex(b));
    concrete.forEach((name) => claimed.add(name));
    if (pad.presence === "always") {
      handles.push(make(pad.name, pad, "always"));
      claimed.add(pad.name);
    } else if (pad.presence === "request") {
      handles.push(...concrete.map((name) => make(name, pad, "request")));
      handles.push(make(pad.name, pad, "request-new", `+ ${pad.name}`));
      claimed.add(pad.name);
    } else {
      handles.push(make(pad.name, pad, "sometimes"));
      handles.push(...concrete.map((name) => make(name, pad, "sometimes")));
      claimed.add(pad.name);
    }
  }
  for (const name of used.filter((n) => !claimed.has(n))) {
    handles.push({ id: name, label: name, direction, presence: "unknown", kind: "orphan", mediaTypes: [], template: name });
  }
  return handles;
}

export function computeHandles(pads: PadSummary[] | undefined, node: GraphNode, edges: GraphEdge[]): NodeHandles {
  const known = pads ?? [];
  return {
    sinks: handlesFor(known, usedPads(node.id, edges, "sink"), "sink"),
    srcs: handlesFor(known, usedPads(node.id, edges, "src"), "src"),
  };
}
