import { useMemo, useState } from "react";
import type { ComponentPort } from "../../api/dynamic";
import type { ElementInfo, GraphEdge, GraphNode } from "../../api/types";
import { Icon } from "../../components/Icon";
import { exposePort, portsOfNode, removePort, suggestPortName } from "../../lib/components";
import { findTemplate, usedPads } from "../../lib/pads";
import { useComponentStore, useCurrentSession } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";

/** Pads of an inner element that can become ports: its templates and the pads already in use. */
function candidatePads(node: GraphNode, details: ElementInfo | undefined, edges: GraphEdge[]): string[] {
  const used = [...usedPads(node.id, edges, "sink"), ...usedPads(node.id, edges, "src")];
  const templates = details?.pad_templates.map((template) => template.name) ?? [];
  return [...new Set([...templates, ...used])];
}

/** Inside a component: which pads of this element are the component's ports. */
export function PortsSection({ node, details }: { node: GraphNode; details: ElementInfo | undefined }) {
  const session = useCurrentSession();
  const edges = useGraphStore((state) => state.graph.edges);
  const update = useComponentStore((state) => state.update);
  const pads = useMemo(() => candidatePads(node, details, edges), [node, details, edges]);
  const [pad, setPad] = useState("");
  const [name, setName] = useState("");
  if (!session) return null;

  const exposed = portsOfNode(session.ports, node.id);
  const chosen = pad || pads.find((p) => !exposed[p]) || "";
  const template = details ? findTemplate(details.pad_templates, chosen) : undefined;
  const direction: ComponentPort["direction"] = template?.direction === "sink" ? "sink" : "src";
  const portName = name || suggestPortName(chosen, session.ports.map((p) => p.name));
  const expose = () => {
    if (!chosen) return;
    update({ ports: exposePort(session.ports, { name: portName, direction, node_id: node.id, pad: chosen }) });
    setPad("");
    setName("");
  };

  return (
    <section className="inspector-section ports-section">
      <h3>Component ports</h3>
      {Object.entries(exposed).map(([padName, port]) => (
        <div key={padName} className="row port-row">
          <span className="port-marker-chip">⇥ {port}</span>
          <span className="mono faint">{padName}</span>
          <span className="spacer" />
          <button className="icon-btn" aria-label={`Unexpose ${port}`} title="Stop exposing this pad"
            onClick={() => update({ ports: removePort(session.ports, port) })}>
            <Icon name="trash" size={12} />
          </button>
        </div>
      ))}
      <div className="row wrap">
        <select className="select" value={chosen} aria-label="Pad to expose" onChange={(event) => setPad(event.target.value)}>
          {pads.map((p) => <option key={p} value={p}>{p}{exposed[p] ? " (exposed)" : ""}</option>)}
        </select>
        <input className="input input-sm mono" value={portName} aria-label="Port name"
          onChange={(event) => setName(event.target.value)} />
        <button className="btn btn-sm" onClick={expose} disabled={!chosen}
          title={`Instances get a ${direction === "sink" ? "sink (input)" : "src (output)"} pad named ${portName}`}>
          <Icon name="export" size={12} /> Expose as port
        </button>
      </div>
    </section>
  );
}
