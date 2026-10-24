import { useMemo } from "react";
import type { PropertyInfo, PropertyValue } from "../../api/types";
import { useElementDetails } from "../../hooks/useElementDetails";
import { previewKind } from "../../lib/elementKinds";
import { isLiveEditable } from "../../lib/propertyValues";
import { usedPads } from "../../lib/pads";
import { useCatalogStore } from "../../store/catalogStore";
import { useGraphStore } from "../../store/graphStore";
import { hasWorker, isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";
import { sendLiveProperty } from "../actions";
import { isComponentFactory } from "../../lib/components";
import { useCurrentSession, useRuntimePrefix } from "../../store/componentStore";
import { InstanceSection } from "../blocks/InstanceSection";
import { PortsSection } from "../blocks/PortsSection";
import { useExposeParam } from "../blocks/useExposeParam";
import { Collapsible } from "./Collapsible";
import { ElementInfoSection } from "./ElementInfoSection";
import { LiveValues } from "./LiveValues";
import { NodeHeader } from "./NodeHeader";
import { PadProperties } from "./PadProperties";
import { PadTemplates } from "./PadTemplates";
import { PropertyList } from "./PropertyList";

export function NodeInspector({ nodeId }: { nodeId: string }) {
  const node = useGraphStore((state) => state.graph.nodes.find((n) => n.id === nodeId));
  const edges = useGraphStore((state) => state.graph.edges);
  const setProperty = useGraphStore((state) => state.setProperty);
  const updateNode = useGraphStore((state) => state.updateNode);
  const summary = useCatalogStore((state) => (node ? state.byName[node.factory] : undefined));
  const inScope = useCurrentSession() !== undefined;
  const prefix = useRuntimePrefix();
  // Inside a component the definition is edited, not the running instance: no live changes.
  const running = useRuntimeStore((state) => isActive(state.state)) && !inScope;
  const inspectable = useRuntimeStore((state) => hasWorker(state.state)) && prefix !== null;
  const exposer = useExposeParam(node);
  const details = useElementDetails(node?.factory);
  const pads = useMemo(
    () => (node ? [...usedPads(node.id, edges, "sink"), ...usedPads(node.id, edges, "src")] : []),
    [node, edges],
  );

  if (!node) return null;

  const onChange = (prop: PropertyInfo, value: PropertyValue | undefined) => {
    setProperty(node.id, prop.name, value);
    if (running && value !== undefined && isLiveEditable(prop)) {
      void sendLiveProperty({ node_id: node.id, property: prop.name, value });
    }
  };
  const onTryLive = (prop: PropertyInfo) => {
    const value = node.properties[prop.name] ?? prop.default;
    if (value !== null && value !== undefined) void sendLiveProperty({ node_id: node.id, property: prop.name, value });
  };

  const preview = previewKind(summary);
  const instance = isComponentFactory(node.factory);
  return (
    <div className="inspector-scroll">
      <NodeHeader node={node} summary={summary} />
      {instance ? <InstanceSection node={node} summary={summary} /> : null}
      {preview ? (
        <div className="inspector-section row">
          <span className="spacer muted">
            Browser preview of this {preview} sink
          </span>
          <label className="switch" title="When on, the runtime replaces this sink by a browser preview">
            <input type="checkbox" checked={node.preview !== "off"} aria-label="Browser preview"
              onChange={(e) => updateNode(node.id, { preview: e.target.checked ? "auto" : "off" })} />
            <span />
          </label>
        </div>
      ) : null}
      {!summary ? (
        <div className="inspector-section badge error">This element is not installed in the runtime image.</div>
      ) : null}
      <Collapsible title={instance ? "Parameters" : "Properties"} defaultOpen>
        {instance && details && !details.properties.some((prop) => prop.writable) ? (
          <p className="muted">No parameters: open the component and expose inner properties to set them per instance.</p>
        ) : details ? (
          <PropertyList properties={details.properties} values={node.properties} running={running} pads={pads}
            onChange={onChange} onTryLive={onTryLive} extra={exposer.extra} />
        ) : summary ? (
          <span className="spinner" />
        ) : null}
      </Collapsible>
      {details ? <PadProperties node={node} details={details} edges={edges} running={running} extra={exposer.extra} /> : null}
      {inScope ? <PortsSection node={node} details={details} /> : null}
      {inspectable ? (
        <Collapsible title="Live values">
          <LiveValues nodeId={`${prefix ?? ""}${node.id}`} />
        </Collapsible>
      ) : null}
      {details ? (
        <>
          <Collapsible title={`Pad templates (${details.pad_templates.length})`}>
            <PadTemplates templates={details.pad_templates} />
          </Collapsible>
          <Collapsible title="Element info">
            <ElementInfoSection info={details} />
          </Collapsible>
        </>
      ) : null}
      <div className="inspector-section">
        <button className="btn btn-danger" onClick={() => {
          useGraphStore.getState().removeElements([node.id], []);
          useUiStore.getState().select([], []);
        }}>
          Delete element
        </button>
      </div>
      {exposer.dialog}
    </div>
  );
}
