import type { ReactNode } from "react";
import type { ElementInfo, GraphEdge, GraphNode, PropertyInfo, PropertyValue } from "../../api/types";
import { findTemplate, usedPads } from "../../lib/pads";
import { isLiveEditable } from "../../lib/propertyValues";
import { useGraphStore } from "../../store/graphStore";
import { sendLiveProperty } from "../actions";
import { Collapsible } from "./Collapsible";
import { PropertyList } from "./PropertyList";

interface PadPropertiesProps {
  node: GraphNode;
  details: ElementInfo;
  edges: GraphEdge[];
  running: boolean;
  extra?: (prop: PropertyInfo, pad: string) => ReactNode;
}

/** Properties of request pads in use, e.g. compositor sink_0 xpos/ypos/alpha. */
export function PadProperties({ node, details, edges, running, extra }: PadPropertiesProps) {
  const setPadProperty = useGraphStore((state) => state.setPadProperty);
  const pads = [...usedPads(node.id, edges, "sink"), ...usedPads(node.id, edges, "src")]
    .map((pad) => ({ pad, template: findTemplate(details.pad_templates, pad) }))
    .filter(({ template }) => template && template.presence === "request")
    .map(({ pad, template }) => ({ pad, properties: template?.properties ?? [] }))
    .filter(({ properties }) => properties.some((p) => p.writable));

  if (pads.length === 0) return null;

  const change = (pad: string) => (prop: PropertyInfo, value: PropertyValue | undefined) => {
    setPadProperty(node.id, pad, prop.name, value);
    if (running && value !== undefined && isLiveEditable(prop)) {
      void sendLiveProperty({ node_id: node.id, property: prop.name, value, pad });
    }
  };
  const tryLive = (pad: string) => (prop: PropertyInfo) => {
    const value = node.pad_properties[pad]?.[prop.name] ?? prop.default;
    if (value !== null && value !== undefined) void sendLiveProperty({ node_id: node.id, property: prop.name, value, pad });
  };

  return (
    <>
      {pads.map(({ pad, properties }) => (
        <Collapsible key={pad} title={`Pad ${pad}`} defaultOpen={pads.length <= 2}>
          <PropertyList properties={properties} values={node.pad_properties[pad] ?? {}} running={running} pads={[]}
            onChange={change(pad)} onTryLive={tryLive(pad)} searchable={false}
            extra={extra ? (prop) => extra(prop, pad) : undefined} />
        </Collapsible>
      ))}
    </>
  );
}
