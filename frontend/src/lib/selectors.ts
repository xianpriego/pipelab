// input-selector / output-selector: which request pad is active and which links carry dropped data.

import type { ElementSummary, Graph, GraphEdge, GraphNode, PadDirection, PropertyValue } from "../api/types";
import type { LiveProps } from "../store/runtimeReducer";
import { templateRegex } from "./pads";

export const ACTIVE_PAD = "active-pad";

export interface SelectorInfo {
  /** Side whose request pads the element chooses from (sink for input-selector). */
  direction: PadDirection;
  /** Linked request pads of that side, by index. */
  pads: string[];
  active: string | null;
}

/** The side an "active-pad" property chooses from: the element's request pads. */
export function selectorDirection(summary: ElementSummary | undefined): PadDirection | null {
  if (!summary?.selectors?.includes(ACTIVE_PAD)) return null;
  return summary.pads.find((pad) => pad.presence === "request")?.direction ?? null;
}

function padIndex(name: string): number {
  const match = /(\d+)(?!.*\d)/.exec(name);
  return match ? Number(match[1]) : 0;
}

export function selectorPads(node: GraphNode, summary: ElementSummary, edges: GraphEdge[], direction: PadDirection): string[] {
  const templates = summary.pads.filter((pad) => pad.presence === "request" && pad.direction === direction);
  const names = edges
    .filter((edge) => (direction === "sink" ? edge.target === node.id : edge.source === node.id))
    .map((edge) => (direction === "sink" ? edge.target_pad : edge.source_pad))
    .filter((name) => templates.some((template) => templateRegex(template.name).test(name)));
  return [...new Set(names)].sort((a, b) => padIndex(a) - padIndex(b));
}

/** Live value while running, else the configured one, else GStreamer's default (the first pad). */
export function resolveActivePad(
  node: GraphNode, pads: string[], live?: Record<string, PropertyValue>,
): string | null {
  const liveValue = live?.[ACTIVE_PAD];
  if (typeof liveValue === "string" && liveValue) return liveValue;
  const configured = node.properties[ACTIVE_PAD];
  if (typeof configured === "string" && pads.includes(configured)) return configured;
  return pads[0] ?? null;
}

export function selectorInfo(
  node: GraphNode, summary: ElementSummary | undefined, edges: GraphEdge[], live?: Record<string, PropertyValue>,
): SelectorInfo | null {
  const direction = selectorDirection(summary);
  if (!summary || !direction) return null;
  const pads = selectorPads(node, summary, edges, direction);
  return { direction, pads, active: resolveActivePad(node, pads, live) };
}

/** Links through a non-active selector pad: buffers reach the selector but are dropped there. */
export function discardedEdges(
  graph: Graph, byName: Record<string, ElementSummary>, liveProps: LiveProps,
): Set<string> {
  const discarded = new Set<string>();
  for (const node of graph.nodes) {
    const info = selectorInfo(node, byName[node.factory], graph.edges, liveProps[node.id]);
    if (!info?.active) continue;
    for (const edge of graph.edges) {
      const pad = info.direction === "sink"
        ? (edge.target === node.id ? edge.target_pad : null)
        : (edge.source === node.id ? edge.source_pad : null);
      if (pad && info.pads.includes(pad) && pad !== info.active) discarded.add(edge.id);
    }
  }
  return discarded;
}
