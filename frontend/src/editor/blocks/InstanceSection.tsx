import type { ElementSummary, GraphNode } from "../../api/types";
import { Icon } from "../../components/Icon";
import { componentIdOf } from "../../lib/components";
import { useComponentStore } from "../../store/componentStore";
import { enterInstance, expandInstance } from "./componentActions";

/** Header actions of a component instance: open its definition or replace it by its elements. */
export function InstanceSection({ node, summary }: { node: GraphNode; summary: ElementSummary | undefined }) {
  const id = componentIdOf(node.factory);
  const def = useComponentStore((state) => state.library.find((component) => component.id === id));
  if (!id) return null;
  return (
    <section className="inspector-section instance-section">
      <div className="row">
        <span className="component-glyph" aria-hidden>▣</span>
        <strong>{def?.name ?? summary?.long_name ?? id}</strong>
        {def ? <span className="badge">v{def.version}</span> : null}
        <span className="spacer" />
      </div>
      {def?.description || summary?.description ? (
        <p className="muted">{def?.description || summary?.description}</p>
      ) : null}
      <p className="faint">
        {def ? `${def.graph.nodes.length} elements · ${def.ports.length} ports · ${def.parameters.length} parameters` : null}
      </p>
      <div className="row wrap">
        <button className="btn btn-sm btn-primary" onClick={() => void enterInstance(node.id)}
          title="Open the definition (double-click the node does the same)">
          <Icon name="graph" size={12} /> Edit component
        </button>
        <button className="btn btn-sm" onClick={() => void expandInstance(node.id)}
          title="Replace this instance by a copy of its elements (no longer linked to the library)">
          <Icon name="layout" size={12} /> Expand into elements
        </button>
      </div>
    </section>
  );
}
