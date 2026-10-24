import {
  Background, BackgroundVariant, Controls, MiniMap, ReactFlow, ReactFlowProvider,
  type Edge,
} from "@xyflow/react";
import { useMemo } from "react";
import type { ElementSummary, MonitorPipeline, MonitorStats } from "../api/types";
import { formatBitrate, formatFps } from "../lib/format";
import { useCatalogStore } from "../store/catalogStore";
import { MonitorNode, type MonitorFlowNode } from "./MonitorNode";

const nodeTypes = { monitor: MonitorNode };
const FIT = { maxZoom: 1.1, padding: 0.08 };

function buildNodes(
  pipeline: MonitorPipeline,
  byName: Record<string, ElementSummary>,
  stats: MonitorStats | null,
): MonitorFlowNode[] {
  const sinks: Record<string, string[]> = {};
  const srcs: Record<string, string[]> = {};
  for (const edge of pipeline.edges) {
    (srcs[edge.source] ??= []).push(edge.source_pad);
    (sinks[edge.target] ??= []).push(edge.target_pad);
  }
  return pipeline.nodes.map((node) => ({
    id: node.id,
    type: "monitor" as const,
    position: node.position,
    data: {
      node,
      summary: node.factory_known ? byName[node.factory] : undefined,
      sinks: dedupe(sinks[node.id]),
      srcs: dedupe(srcs[node.id]),
      latency: stats?.elements?.[node.id] ?? null,
    },
  }));
}

function dedupe(pads: string[] | undefined): string[] {
  return pads ? [...new Set(pads)] : [];
}

function buildEdges(pipeline: MonitorPipeline, stats: MonitorStats | null): Edge[] {
  return pipeline.edges.map((edge) => {
    const flow = stats?.edges?.[edge.id];
    const active = !!flow && flow.fps > 0;
    const label = flow
      ? `${formatFps(flow.fps)} · ${formatBitrate(flow.bitrate)}`
      : capsSummary(edge.caps);
    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      sourceHandle: edge.source_pad,
      targetHandle: edge.target_pad,
      label,
      labelShowBg: true,
      animated: active,
      className: `monitor-edge${active ? " monitor-edge-active" : ""}`,
    };
  });
}

/** Shorten caps to the media type for the edge label; the full string is on the title. */
function capsSummary(caps: string | null): string | undefined {
  if (!caps) return undefined;
  const media = caps.split(/[ ,]/)[0];
  return media || undefined;
}

export function MonitorFlow({ pipeline, stats }: { pipeline: MonitorPipeline; stats: MonitorStats | null }) {
  const catalog = useCatalogStore((s) => s.byName);
  const nodes = useMemo(() => buildNodes(pipeline, catalog, stats), [pipeline, catalog, stats]);
  const edges = useMemo(() => buildEdges(pipeline, stats), [pipeline, stats]);

  return (
    <ReactFlowProvider>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        fitView
        fitViewOptions={FIT}
        nodesConnectable={false}
        nodesDraggable
        elementsSelectable={false}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={18} size={1} />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </ReactFlowProvider>
  );
}
