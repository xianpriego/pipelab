import { useState } from "react";
import { Icon } from "../../components/Icon";
import { useCurrentSession } from "../../store/componentStore";
import { useUiStore } from "../../store/uiStore";
import { deleteSelection } from "../selectionActions";
import { ComponentNameDialog } from "../blocks/ComponentNameDialog";
import { ComponentPanel } from "../blocks/ComponentPanel";
import { groupSelection } from "../blocks/componentActions";
import { EdgeInspector } from "./EdgeInspector";
import { NodeInspector } from "./NodeInspector";
import { ProjectInspector } from "./ProjectInspector";

function SelectionInspector({ nodes, edges }: { nodes: string[]; edges: string[] }) {
  const [grouping, setGrouping] = useState(false);
  return (
    <div className="inspector-section">
      <h3>{nodes.length} elements, {edges.length} links selected</h3>
      <p className="muted">Ctrl+C / Ctrl+V duplicates the selection.</p>
      <div className="row wrap">
        {nodes.length ? (
          <button className="btn btn-primary" onClick={() => setGrouping(true)}
            title="Replace the selected elements by one reusable component">
            <Icon name="graph" size={13} /> Group into component
          </button>
        ) : null}
        <button className="btn btn-danger" onClick={() => deleteSelection(nodes, edges)}>
          Delete selection
        </button>
      </div>
      {grouping ? (
        <ComponentNameDialog title="Group into component" confirmLabel="Group"
          hint={`The ${nodes.length} selected elements move into a library component; links crossing the selection become its ports.`}
          onSubmit={(name, id) => groupSelection(nodes, name, id)} onClose={() => setGrouping(false)} />
      ) : null}
    </div>
  );
}

export function Inspector() {
  const nodes = useUiStore((state) => state.selectedNodes);
  const edges = useUiStore((state) => state.selectedEdges);
  const inComponent = useCurrentSession() !== undefined;

  let content;
  if (nodes.length === 1) content = <NodeInspector key={nodes[0]} nodeId={nodes[0]} />;
  else if (nodes.length === 0 && edges.length === 1) content = <EdgeInspector key={edges[0]} edgeId={edges[0]} />;
  else if (nodes.length + edges.length > 1) content = <SelectionInspector nodes={nodes} edges={edges} />;
  else content = inComponent ? <ComponentPanel /> : <ProjectInspector />;

  return <aside className="inspector">{content}</aside>;
}
