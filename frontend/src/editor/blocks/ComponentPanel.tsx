import type { ComponentParam } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { removeParam, removeParamTarget, removePort, renamePort, updateParam } from "../../lib/components";
import { formatValue, parseValue } from "../../lib/valueRefs";
import { useComponentStore, useCurrentSession } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { deleteCurrentComponent, exportComponentFile } from "./componentActions";
import { notify, useUiStore } from "../../store/uiStore";

function nodeLabel(nodes: { id: string; name: string }[], id: string): string {
  return nodes.find((node) => node.id === id)?.name ?? `${id} (missing)`;
}

function ParamCard({ param }: { param: ComponentParam }) {
  const session = useCurrentSession();
  const nodes = useGraphStore((state) => state.graph.nodes);
  const update = useComponentStore((state) => state.update);
  if (!session) return null;
  const patch = (change: Partial<ComponentParam>) => {
    const next = updateParam(session.parameters, param.name, change);
    if (next) update({ parameters: next });
    else notify({ level: "warning", title: `A parameter "${change.name}" already exists` });
  };
  return (
    <div className="param-card">
      <div className="row">
        <input className="input input-sm mono" defaultValue={param.name} aria-label={`Name of parameter ${param.name}`}
          onBlur={(event) => event.target.value.trim() && event.target.value !== param.name && patch({ name: event.target.value.trim() })} />
        <input className="input input-sm" defaultValue={formatValue(param.default)} placeholder="default"
          aria-label={`Default of ${param.name}`} onBlur={(event) => patch({ default: parseValue(event.target.value) })} />
        <button className="icon-btn" aria-label={`Remove parameter ${param.name}`} title="Remove (the inner values stay)"
          onClick={() => update({ parameters: removeParam(session.parameters, param.name) })}>
          <Icon name="trash" size={12} />
        </button>
      </div>
      <input className="input input-sm" defaultValue={param.description} placeholder="Description shown on instances"
        aria-label={`Description of ${param.name}`} onBlur={(event) => patch({ description: event.target.value })} />
      <ul className="target-list">
        {param.targets.map((target, index) => (
          <li key={`${target.node_id}-${target.pad ?? ""}-${target.property}`} className="row">
            <button className="link-btn mono" onClick={() => useUiStore.getState().select([target.node_id], [])}>
              {nodeLabel(nodes, target.node_id)}{target.pad ? `.${target.pad}` : ""}.{target.property}
            </button>
            <span className="spacer" />
            <button className="icon-btn" aria-label={`Unlink ${target.property} from ${param.name}`}
              onClick={() => update({ parameters: removeParamTarget(session.parameters, param.name, index) })}>
              <Icon name="close" size={11} />
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Inspector of the open component (nothing selected): name, ports and parameters. */
export function ComponentPanel() {
  const session = useCurrentSession();
  const nodes = useGraphStore((state) => state.graph.nodes);
  const update = useComponentStore((state) => state.update);
  if (!session) return null;

  return (
    <div className="inspector-scroll component-panel">
      <div className="inspector-section">
        <h3>Component</h3>
        <label className="field">
          Name
          <input className="input" value={session.name} onChange={(event) => update({ name: event.target.value })} />
        </label>
        <label className="field">
          Description
          <textarea className="textarea" rows={2} value={session.description}
            onChange={(event) => update({ description: event.target.value })} />
        </label>
      </div>
      <div className="inspector-section">
        <h3>Ports <span className="faint">({session.ports.length})</span></h3>
        {session.ports.length === 0 ? (
          <p className="muted">Select an inner element and use <strong>Expose as port</strong> to let data in or out.</p>
        ) : null}
        {session.ports.map((port) => (
          <div key={port.name} className="row port-row">
            <span className={`port-dir ${port.direction}`} title={port.direction === "sink" ? "input" : "output"}>
              {port.direction === "sink" ? "in" : "out"}
            </span>
            <input className="input input-sm mono" defaultValue={port.name} aria-label={`Name of port ${port.name}`}
              onBlur={(event) => {
                const next = renamePort(session.ports, port.name, event.target.value.trim());
                if (next) update({ ports: next });
                else if (event.target.value.trim() !== port.name) notify({ level: "warning", title: "Port names must be unique" });
              }} />
            <button className="link-btn mono faint" onClick={() => useUiStore.getState().select([port.node_id], [])}>
              {nodeLabel(nodes, port.node_id)}.{port.pad}
            </button>
            <span className="spacer" />
            <button className="icon-btn" aria-label={`Remove port ${port.name}`}
              onClick={() => update({ ports: removePort(session.ports, port.name) })}>
              <Icon name="trash" size={12} />
            </button>
          </div>
        ))}
      </div>
      <div className="inspector-section">
        <h3>Parameters <span className="faint">({session.parameters.length})</span></h3>
        {session.parameters.length === 0 ? (
          <p className="muted">Use the <Icon name="export" size={11} /> button of a property row to expose it as a parameter;
            one parameter can drive several inner properties.</p>
        ) : null}
        {session.parameters.map((param) => <ParamCard key={param.name} param={param} />)}
      </div>
      <div className="inspector-section row">
        <button className="btn" onClick={() => void exportComponentFile(session.base.id)}
          title="Downloads the saved definition (with the components it contains) to share it">
          <Icon name="export" size={12} /> Export to file
        </button>
        <button className="btn btn-danger" onClick={() => void deleteCurrentComponent()}
          title="Removes the definition from the library (lists who uses it first)">
          Delete component
        </button>
      </div>
    </div>
  );
}
