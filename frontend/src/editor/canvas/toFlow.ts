// Mapping of the pipeline graph to React Flow nodes and edges.

import type { Edge, Node } from "@xyflow/react";
import type { EdgeStats } from "../../api/events";
import type { ElementSummary, Graph, GraphEdge, GraphNode, Severity } from "../../api/types";
import { previewKind } from "../../lib/elementKinds";
import { computeHandles, type NodeHandles } from "../../lib/pads";
import type { NodePerf, ThreadInfo } from "../../lib/perf";
import type { ProbeMarker } from "../../lib/probeRules";
import type { ScriptMarker } from "../../lib/scripts";
import { ACTIVE_PAD, selectorInfo, type SelectorInfo } from "../../lib/selectors";
import type { LiveProps, NodeAlert } from "../../store/runtimeReducer";

export interface ElementNodeData extends Record<string, unknown> {
  node: GraphNode;
  summary: ElementSummary | undefined;
  handles: NodeHandles;
  severity: Severity | undefined;
  alert: NodeAlert | undefined;
  preview: "video" | "audio" | null;
  /** input/output-selector: pads to choose from and the active one. */
  selector: SelectorInfo | null;
  /** Pad requested from the UI that a script deferred (switch at the next keyframe…). */
  pendingPad: string | null;
  scripts: ScriptMarker | undefined;
  probes: ProbeMarker | undefined;
  /** Inside a component: exposed pads → port names. */
  ports: Record<string, string> | undefined;
  /** While running: latency and queue level. */
  perf: NodePerf | undefined;
}

export type ElementFlowNode = Node<ElementNodeData, "element">;

export interface FlowEdgeData extends Record<string, unknown> {
  severity: Severity | undefined;
  stats: EdgeStats | undefined;
  caps: string | undefined;
  running: boolean;
  /** Data reaches a selector through a non-active pad and is dropped there. */
  discarded: boolean;
  /** Reported by a runtime error/warning (e.g. caps negotiation failed here). */
  alert: NodeAlert | undefined;
  scripts: ScriptMarker | undefined;
  probes: ProbeMarker | undefined;
  /** Streaming thread pushing the link, when links are coloured by thread. */
  thread: ThreadInfo | undefined;
}

export type PipelineFlowEdge = Edge<FlowEdgeData, "flow">;

export interface NodeContext {
  byName: Record<string, ElementSummary>;
  severities: Record<string, Severity>;
  alerts: Record<string, NodeAlert>;
  selected: Set<string>;
  measured: Record<string, { width: number; height: number }>;
  liveProps: LiveProps;
  pending: LiveProps;
  /** Script markers keyed `node:<id>` / `edge:<id>`. */
  markers: Record<string, ScriptMarker>;
  /** No-code probe markers, same keys. */
  probeMarkers?: Record<string, ProbeMarker>;
  /** Exposed ports per node id (inside a component). */
  ports?: Record<string, Record<string, string>>;
  /** Links that are not graph edges but use pads (slot links). */
  extraEdges?: GraphEdge[];
  perf?: Record<string, NodePerf>;
}

export function toFlowNodes(graph: Graph, ctx: NodeContext): ElementFlowNode[] {
  const edges = ctx.extraEdges?.length ? [...graph.edges, ...ctx.extraEdges] : graph.edges;
  return graph.nodes.map((node) => {
    const summary = ctx.byName[node.factory];
    return {
      id: node.id,
      type: "element",
      position: node.position,
      selected: ctx.selected.has(node.id),
      measured: ctx.measured[node.id],
      data: {
        node,
        summary,
        handles: computeHandles(summary?.pads, node, edges),
        severity: ctx.severities[node.id],
        alert: ctx.alerts[node.id],
        preview: node.preview === "off" ? null : previewKind(summary),
        selector: selectorInfo(node, summary, graph.edges, ctx.liveProps[node.id]),
        pendingPad: typeof ctx.pending[node.id]?.[ACTIVE_PAD] === "string"
          ? (ctx.pending[node.id][ACTIVE_PAD] as string)
          : null,
        scripts: ctx.markers[`node:${node.id}`],
        probes: ctx.probeMarkers?.[`node:${node.id}`],
        ports: ctx.ports?.[node.id],
        perf: ctx.perf?.[node.id],
      },
    };
  });
}

export interface EdgeContext {
  severities: Record<string, Severity>;
  stats: Record<string, EdgeStats>;
  caps: Record<string, string>;
  selected: Set<string>;
  running: boolean;
  discarded: Set<string>;
  alerts: Record<string, NodeAlert>;
  markers: Record<string, ScriptMarker>;
  probeMarkers?: Record<string, ProbeMarker>;
  threads?: Record<string, ThreadInfo>;
}

export function toFlowEdges(graph: Graph, ctx: EdgeContext): PipelineFlowEdge[] {
  return graph.edges.map((edge) => ({
    id: edge.id,
    type: "flow",
    source: edge.source,
    sourceHandle: edge.source_pad,
    target: edge.target,
    targetHandle: edge.target_pad,
    selected: ctx.selected.has(edge.id),
    data: {
      severity: ctx.severities[edge.id],
      stats: ctx.stats[edge.id],
      caps: ctx.caps[edge.id],
      running: ctx.running,
      discarded: ctx.discarded.has(edge.id),
      alert: ctx.alerts[edge.id],
      scripts: ctx.markers[`edge:${edge.id}`],
      probes: ctx.probeMarkers?.[`edge:${edge.id}`],
      thread: ctx.threads?.[edge.id],
    },
  }));
}
