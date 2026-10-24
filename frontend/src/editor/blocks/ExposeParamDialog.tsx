import { useState } from "react";
import type { Value } from "../../api/components";
import type { GraphNode, PropertyInfo } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { exposeParam } from "../../lib/components";
import { formatValue, parseValue } from "../../lib/paramValues";
import { useComponentStore, useCurrentSession } from "../../store/componentStore";

interface ExposeParamDialogProps {
  node: GraphNode;
  prop: PropertyInfo;
  pad?: string | null;
  onClose: () => void;
}

const NEW = "";

/** Makes an inner property settable on every instance, as a new or an existing parameter. */
export function ExposeParamDialog({ node, prop, pad = null, onClose }: ExposeParamDialogProps) {
  const session = useCurrentSession();
  const update = useComponentStore((state) => state.update);
  const params = session?.parameters ?? [];
  const current: Value = (pad ? node.pad_properties[pad]?.[prop.name] : node.properties[prop.name]) ?? prop.default ?? null;
  const [existing, setExisting] = useState(NEW);
  const [name, setName] = useState(prop.name.replace(/-/g, "_"));
  const [description, setDescription] = useState(prop.blurb);
  const [defaultText, setDefaultText] = useState(formatValue(current));
  if (!session) return null;

  const target = { node_id: node.id, property: prop.name, pad };
  const taken = existing === NEW && params.some((p) => p.name === name);
  const save = () => {
    const paramName = existing || name.trim();
    update({ parameters: exposeParam(params, paramName, target, description, parseValue(defaultText)) });
    onClose();
  };

  return (
    <Dialog title={`Expose ${node.name}${pad ? `.${pad}` : ""}.${prop.name}`} onClose={onClose} footer={
      <>
        <span className="muted">{taken ? `"${name}" exists: pick it above to add this target` : "Instances show it as a property"}</span>
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={taken || (!existing && !name.trim())}>Expose</button>
      </>
    }>
      <div className="form-grid">
        {params.length ? (
          <label className="field">
            Parameter
            <select className="select" value={existing} onChange={(event) => setExisting(event.target.value)}>
              <option value={NEW}>New parameter…</option>
              {params.map((p) => <option key={p.name} value={p.name}>{p.name} (also drives {p.targets.length})</option>)}
            </select>
          </label>
        ) : null}
        {existing === NEW ? (
          <>
            <label className="field">
              Name
              <input className="input mono" autoFocus value={name} onChange={(event) => setName(event.target.value)} />
            </label>
            <label className="field">
              Description
              <input className="input" value={description} onChange={(event) => setDescription(event.target.value)} />
            </label>
            <label className="field">
              Default
              <input className="input mono" value={defaultText} onChange={(event) => setDefaultText(event.target.value)} />
            </label>
          </>
        ) : (
          <p className="muted">{node.name}.{prop.name} will follow the value of <code>{existing}</code>.</p>
        )}
      </div>
    </Dialog>
  );
}
