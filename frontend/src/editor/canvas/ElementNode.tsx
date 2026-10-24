import { useUpdateNodeInternals, type NodeProps } from "@xyflow/react";
import { memo, useEffect, type CSSProperties } from "react";
import { Icon } from "../../components/Icon";
import { accentColor } from "../../lib/elementKinds";
import type { HandleSpec } from "../../lib/pads";
import { selectActivePad } from "../actions";
import { NodePerfBar } from "./NodePerf";
import { PadHandle, type PadChoice } from "./PadHandle";
import type { ElementFlowNode } from "./toFlow";

function ElementNodeView({ id, data, selected }: NodeProps<ElementFlowNode>) {
  const { node, summary, handles, severity, alert, preview, selector, ports, perf } = data;
  const updateInternals = useUpdateNodeInternals();
  const signature = [...handles.sinks, ...handles.srcs].map((h) => h.id).join("|");

  useEffect(() => {
    updateInternals(id);
  }, [id, signature, updateInternals]);

  const choice = (spec: HandleSpec): PadChoice | undefined => {
    if (!selector || spec.direction !== selector.direction || !selector.pads.includes(spec.id)) return undefined;
    return {
      active: selector.active === spec.id,
      onSelect: () => void selectActivePad(node.id, spec.id),
    };
  };
  const status = alert ?? severity;
  const component = summary?.family === "component";
  const classes = [
    "element-node", component ? "component-node" : "", status ? `status-${status}` : "", selected ? "selected" : "",
  ].join(" ");
  return (
    <div className={classes} style={{ "--accent": accentColor(summary) } as CSSProperties}>
      <div className="element-node-header">
        {component ? <span className="component-glyph" title="Component: double-click to open it">▣</span> : null}
        <span className="element-node-name" title={node.name}>{node.name}</span>
        {preview ? (
          <span className="element-node-icon" title={`Previewed in the browser (${preview})`}>
            <Icon name={preview === "video" ? "eye" : "speaker"} size={13} />
          </span>
        ) : null}
        {summary ? <span className={`family-badge family-${summary.family}`}>{summary.family}</span> : null}
      </div>
      <div className="element-node-factory" title={summary?.long_name ?? "Element not installed"}>
        {summary ? node.factory : `${node.factory} (not installed)`}
      </div>
      <div className="element-node-pads">
        <div className="pads-col">
          {handles.sinks.map((spec) => (
            <PadHandle key={`in-${spec.id}`} spec={spec} choice={choice(spec)} port={ports?.[spec.id]} />
          ))}
        </div>
        <div className="pads-col srcs">
          {handles.srcs.map((spec) => (
            <PadHandle key={`out-${spec.id}`} spec={spec} choice={choice(spec)} port={ports?.[spec.id]} />
          ))}
        </div>
      </div>
      {perf ? <NodePerfBar perf={perf} /> : null}
    </div>
  );
}

export const ElementNode = memo(ElementNodeView);
