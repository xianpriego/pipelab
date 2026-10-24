import { useUpdateNodeInternals, type NodeProps } from "@xyflow/react";
import { memo, useEffect } from "react";
import { formatBitrate, formatFps } from "../../lib/format";
import { PadHandle } from "../canvas/PadHandle";
import type { SlotFlowNode } from "./slotFlow";

/** A slot: a stack of N instances of one component, created and removed while running. */
function SlotNodeView({ id, data, selected }: NodeProps<SlotFlowNode>) {
  const { slot, summary, handles, instances, running, severity, rates } = data;
  const updateInternals = useUpdateNodeInternals();
  const signature = [...handles.sinks, ...handles.srcs].map((h) => h.id).join("|");

  useEffect(() => {
    updateInternals(id);
  }, [id, signature, updateInternals]);

  const max = slot.max_instances ? ` / ${slot.max_instances}` : "";
  const classes = ["slot-node", severity ? `status-${severity}` : "", selected ? "selected" : "", running ? "live" : ""];
  return (
    <div className={classes.join(" ")} data-testid={`slot-${slot.name}`}>
      <div className="element-node-header">
        <span key={instances.length} className="slot-count" title={running ? "Live instances" : "Instances created at start"}>
          ×{instances.length}{max}
        </span>
        <span className="element-node-name" title={slot.name}>{slot.name}</span>
        <span className="family-badge family-slot">slot</span>
      </div>
      <div className="element-node-factory" title={summary?.long_name ?? `component:${slot.component} not found`}>
        {summary ? slot.component : `${slot.component} (missing)`} · add_{slot.item}()
      </div>
      <div className="element-node-pads">
        <div className="pads-col">
          {handles.sinks.map((spec) => <PadHandle key={`in-${spec.id}`} spec={spec} />)}
        </div>
        <div className="pads-col srcs">
          {handles.srcs.map((spec) => <PadHandle key={`out-${spec.id}`} spec={spec} />)}
        </div>
      </div>
      {rates.map((rate) => (
        <div key={rate.port} className="slot-rate mono" title={`Sum over the instances of port ${rate.port}`}>
          {rate.port}: {rate.flowing} flowing · {formatFps(rate.fps)} · {formatBitrate(rate.bitrate)}
        </div>
      ))}
      {instances.length ? (
        <div className="slot-instances">
          {instances.slice(0, 6).map((instance) => <span key={instance.id} className="slot-chip mono">{instance.id}</span>)}
          {instances.length > 6 ? <span className="faint">+{instances.length - 6}</span> : null}
        </div>
      ) : null}
    </div>
  );
}

export const SlotNode = memo(SlotNodeView);
