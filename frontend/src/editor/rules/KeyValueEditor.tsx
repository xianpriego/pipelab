import { useState } from "react";
import type { Value } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { ValueInput } from "./ValueInput";

interface KeyValueEditorProps {
  value: Record<string, Value> | undefined;
  onChange: (value: Record<string, Value>) => void;
  label: string;
  /** Known keys offered in a datalist (function arguments, component parameters…). */
  keys?: string[];
}

/** Ordered key → value map (message fields, call arguments, instance parameters). */
export function KeyValueEditor({ value, onChange, label, keys = [] }: KeyValueEditorProps) {
  const entries = Object.entries(value ?? {});
  const [draftKey, setDraftKey] = useState("");
  const listId = `kv-${label.replace(/\W+/g, "-")}`;

  const setEntry = (index: number, key: string, entryValue: Value) => {
    const next = entries.map(([k, v], i) => (i === index ? [key, entryValue] : [k, v]) as [string, Value]);
    onChange(Object.fromEntries(next));
  };
  const remove = (index: number) => onChange(Object.fromEntries(entries.filter((_e, i) => i !== index)));
  const add = () => {
    const key = draftKey.trim();
    if (!key || key in (value ?? {})) return;
    onChange({ ...(value ?? {}), [key]: null });
    setDraftKey("");
  };

  return (
    <div className="kv-editor" aria-label={label}>
      {entries.map(([key, entryValue], index) => (
        <div className="kv-row" key={`${key}-${index}`}>
          <input className="input input-sm mono kv-key" value={key} aria-label={`${label} key`}
            onChange={(event) => setEntry(index, event.target.value, entryValue)} />
          <ValueInput value={entryValue} label={`${label} ${key}`} onChange={(v) => setEntry(index, key, v)} />
          <button type="button" className="icon-btn" aria-label={`Remove ${key}`} onClick={() => remove(index)}>
            <Icon name="close" size={12} />
          </button>
        </div>
      ))}
      <div className="kv-row">
        <input className="input input-sm mono kv-key" placeholder="new key" value={draftKey} list={keys.length ? listId : undefined}
          aria-label={`New ${label} key`} onChange={(event) => setDraftKey(event.target.value)}
          onKeyDown={(event) => event.key === "Enter" && add()} />
        {keys.length ? (
          <datalist id={listId}>{keys.map((k) => <option key={k} value={k} />)}</datalist>
        ) : null}
        <button type="button" className="btn btn-sm" onClick={add} disabled={!draftKey.trim()}>
          <Icon name="plus" size={12} /> Add
        </button>
      </div>
    </div>
  );
}
