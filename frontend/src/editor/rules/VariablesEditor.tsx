import { useState } from "react";
import type { Value } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { formatValue, parseValue } from "../../lib/valueRefs";

interface VariablesEditorProps {
  variables: Record<string, Value>;
  onChange: (variables: Record<string, Value>) => void;
}

/** Variables of a rule set with their initial values (per instance inside components). */
export function VariablesEditor({ variables, onChange }: VariablesEditorProps) {
  const [name, setName] = useState("");
  const entries = Object.entries(variables);
  const add = () => {
    const key = name.trim().replace(/\W+/g, "_");
    if (!key || key in variables) return;
    onChange({ ...variables, [key]: 0 });
    setName("");
  };
  return (
    <div className="variables-editor">
      {entries.length === 0 ? <span className="faint">No variables. Use them as counters or flags ($name).</span> : null}
      {entries.map(([key, value]) => (
        <div key={key} className="kv-row">
          <span className="mono var-name">${key}</span>
          <input className="input input-sm mono" aria-label={`Initial value of ${key}`} defaultValue={formatValue(value)}
            onChange={(event) => onChange({ ...variables, [key]: parseValue(event.target.value) })} />
          <button type="button" className="icon-btn" aria-label={`Remove variable ${key}`} onClick={() => {
            const next = { ...variables };
            delete next[key];
            onChange(next);
          }}>
            <Icon name="close" size={12} />
          </button>
        </div>
      ))}
      <div className="kv-row">
        <input className="input input-sm mono" placeholder="new variable" value={name} aria-label="New variable name"
          onChange={(event) => setName(event.target.value)} onKeyDown={(event) => event.key === "Enter" && add()} />
        <button type="button" className="btn btn-sm" onClick={add} disabled={!name.trim()}>
          <Icon name="plus" size={12} /> Variable
        </button>
      </div>
    </div>
  );
}
