// Slots on the canvas: one stacked node per slot and dashed links to the static graph.

import type { Edge, Node } from "@xyflow/react";
import type { Slot, SlotInstance } from "../../api/dynamic";
import type { EdgeStats } from "../../api/events";
import type { ElementSummary, Graph, GraphEdge, PadSummary, Severity } from "../../api/types";
import { COMPONENT_PREFIX } from "../../lib/components";
import type { HandleSpec, NodeHandles } from "../../lib/pads";
import { shownInstances, slotPosition, slotsOf } from "../../lib/slots";

export const SLOT_NODE_PREFIX = "slot:";

export function slotNodeId(slotId: string): string {
  return `${SLOT_NODE_PREFIX}${slotId}`;
}

export function slotIdOf(nodeId: string): string | null {
  return nodeId.startsWith(SLOT_NODE_PREFIX) ? nodeId.slice(SLOT_NODE_PREFIX.length) : null;
}

export interface SlotNodeData extends Record<string, unknown> {
  slot: Slot;
  summary: ElementSummary | undefined;
  handles: NodeHandles;
  instances: SlotInstance[];
  running: boolean;
  severity: Severity | undefined;
  /** Live totals per linked port, while running. */
  rates: { port: string; flowing: number; fps: number; bitrate: number }[];
}

export type SlotFlowNode = Node<SlotNodeData, "slot">;

export interface SlotContext {
  byName: Record<string, ElementSummary>;
  live: Record<string, SlotInstance[]>;
  running: boolean;
  selected: Set<string>;
  /** Positions being dragged (not saved yet). */
  positions: Record<string, { x: number; y: number }>;
  severities: Record<string, Severity>;
  /** Link stats of the run (slot ports use "<slot>.<instance>:<port>"). */
  stats?: Record<string, EdgeStats>;
}

function portPads(slot: Slot, byName: Record<string, ElementSummary>): PadSummary[] {
  return byName[`${COMPONENT_PREFIX}${slot.component}`]?.pads ?? [];
}

function portHandle(pad: PadSummary): HandleSpec {
  return {
    id: pad.name, label: pad.name, direction: pad.direction, presence: "always", kind: "always",
    mediaTypes: pad.media_types, template: pad.name,
  };
}

function portDirection(slot: Slot, port: string, byName: Record<string, ElementSummary>): "src" | "sink" {
  return portPads(slot, byName).find((pad) => pad.name === port)?.direction === "sink" ? "sink" : "src";
}

export function toSlotNodes(graph: Graph, ctx: SlotContext): SlotFlowNode[] {
  return slotsOf(graph).map((slot, index) => {
    const pads = portPads(slot, ctx.byName);
    const consumer = slot.links.some((link) => portDirection(slot, link.port, ctx.byName) === "sink");
    const id = slotNodeId(slot.id);
    return {
      id,
      type: "slot",
      position: ctx.positions[id] ?? slotPosition(slot, graph, index, consumer),
      selected: ctx.selected.has(id),
      data: {
        slot,
        summary: ctx.byName[`${COMPONENT_PREFIX}${slot.component}`],
        handles: {
          sinks: pads.filter((pad) => pad.direction === "sink").map(portHandle),
          srcs: pads.filter((pad) => pad.direction === "src").map(portHandle),
        },
        instances: shownInstances(slot, ctx.live, ctx.running),
        running: ctx.running,
        severity: ctx.severities[slot.id],
        rates: ctx.running ? slotRates(slot, ctx.stats ?? {}) : [],
      },
    };
  });
}

function slotLinkId(slotId: string, index: number): string {
  return `slotlink:${slotId}:${index}`;
}

/** Static-graph edges equivalent to the slot links (so linked nodes show the pads they use). */
export function slotLinkEdges(graph: Graph, byName: Record<string, ElementSummary>): GraphEdge[] {
  return slotsOf(graph).flatMap((slot) => slot.links.map((link, index) => {
    const id = slotLinkId(slot.id, index);
    const fromSlot = portDirection(slot, link.port, byName) === "src";
    return fromSlot
      ? { id, source: slotNodeId(slot.id), source_pad: link.port, target: link.node_id, target_pad: link.pad }
      : { id, source: link.node_id, source_pad: link.pad, target: slotNodeId(slot.id), target_pad: link.port };
  }));
}

function slotRates(slot: Slot, stats: Record<string, EdgeStats>): SlotNodeData["rates"] {
  const ports = [...new Set(slot.links.map((link) => link.port))];
  return ports.flatMap((port) => {
    const live = slotPortStats(slot.id, port, stats);
    return live ? [{ port, ...live }] : [];
  });
}

/** Totals of one port over the live instances (stats ids are "<slot>.<instance>:<port>"). */
export function slotPortStats(slotId: string, port: string, stats: Record<string, EdgeStats>):
  { flowing: number; fps: number; bitrate: number } | null {
  const prefix = `${slotId}.`;
  const suffix = `:${port}`;
  const ports = Object.entries(stats).filter(([id]) => id.startsWith(prefix) && id.endsWith(suffix));
  if (!ports.length) return null;
  return {
    flowing: ports.filter(([, stat]) => stat.fps > 0).length,
    fps: ports.reduce((sum, [, stat]) => sum + stat.fps, 0),
    bitrate: ports.reduce((sum, [, stat]) => sum + stat.bitrate, 0),
  };
}

export function toSlotEdges(graph: Graph, byName: Record<string, ElementSummary>): Edge[] {
  const nodes = new Set(graph.nodes.map((node) => node.id));
  return slotLinkEdges(graph, byName)
    .filter((edge) => nodes.has(edge.source) || nodes.has(edge.target))
    .map((edge) => ({
      id: edge.id, source: edge.source, sourceHandle: edge.source_pad, target: edge.target, targetHandle: edge.target_pad,
      type: "default", className: "slot-link", selectable: false, deletable: false, focusable: false,
    }));
}
