import { Handle, Position, type NodeProps, type Node } from "@xyflow/react";
import { memo, type CSSProperties } from "react";
import { accentColor } from "../lib/elementKinds";
import { formatMs } from "../lib/perf";
import type { ElementSummary, MonitorElementLatency, MonitorNode as MonitorNodeModel } from "../api/types";

export interface MonitorNodeData extends Record<string, unknown> {
  node: MonitorNodeModel;
  summary: ElementSummary | undefined;
  sinks: string[];
  srcs: string[];
  latency: MonitorElementLatency | null;
}

export type MonitorFlowNode = Node<MonitorNodeData, "monitor">;

const STATE_LABEL: Record<string, string> = {
  playing: "playing",
  paused: "paused",
  ready: "ready",
  null: "null",
  "void-pending": "pending",
};

function MonitorNodeView({ data }: NodeProps<MonitorFlowNode>) {
  const { node, summary, sinks, srcs, latency } = data;
  const props = Object.entries(node.properties).slice(0, 4);
  return (
    <div
      className={`monitor-node${node.is_bin ? " monitor-node-bin" : ""}`}
      style={{ "--accent": summary ? accentColor(summary) : "var(--accent-generic)" } as CSSProperties}
    >
      <div className="monitor-node-header">
        {node.is_bin ? <span className="monitor-glyph" title="Bin (contains other elements)">▣</span> : null}
        <span className="monitor-node-name" title={node.name}>{node.name}</span>
        {node.state ? (
          <span className={`monitor-state monitor-state-${node.state}`}>{STATE_LABEL[node.state] ?? node.state}</span>
        ) : null}
      </div>
      <div
        className="monitor-node-type"
        title={node.factory_known ? `${node.gtype} — factory ${node.factory}` : `${node.gtype} (factory not on this machine)`}
      >
        {node.gtype}
      </div>
      {latency ? (
        <div className="monitor-node-latency" title={`time inside this element · max ${formatMs(latency.max_ms)}`}>
          <span>latency</span>
          <strong>{formatMs(latency.avg_ms)}</strong>
        </div>
      ) : null}
      {props.length ? (
        <dl className="monitor-node-props">
          {props.map(([key, value]) => (
            <div key={key} className="monitor-prop">
              <dt title={key}>{key}</dt>
              <dd title={value}>{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
      {sinks.map((pad, i) => (
        <Handle
          key={`in-${pad}`}
          id={pad}
          type="target"
          position={Position.Left}
          style={{ top: `${handleTop(i, sinks.length)}%` }}
          isConnectable={false}
        />
      ))}
      {srcs.map((pad, i) => (
        <Handle
          key={`out-${pad}`}
          id={pad}
          type="source"
          position={Position.Right}
          style={{ top: `${handleTop(i, srcs.length)}%` }}
          isConnectable={false}
        />
      ))}
    </div>
  );
}

function handleTop(index: number, count: number): number {
  return ((index + 1) / (count + 1)) * 100;
}

export const MonitorNode = memo(MonitorNodeView);
