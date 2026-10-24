import type { FieldSpec, Value } from "../../api/dynamic";
import { useRuleEditor, type Choice } from "./editorContext";
import { KeyValueEditor } from "./KeyValueEditor";
import { ValueInput } from "./ValueInput";

interface FieldInputProps {
  field: FieldSpec;
  value: unknown;
  /** Other fields of the same object (e.g. the chosen element for a property field). */
  siblings: Record<string, unknown>;
  onChange: (value: unknown) => void;
}

const NUMERIC = new Set(["int", "ms", "float", "percent"]);

function Select({ label, value, choices, onChange, empty }: {
  label: string; value: unknown; choices: Choice[]; onChange: (v: string | null) => void; empty?: string;
}) {
  return (
    <select className="select select-sm" aria-label={label} value={typeof value === "string" ? value : ""}
      onChange={(event) => onChange(event.target.value || null)}>
      <option value="">{empty ?? "—"}</option>
      {choices.map((choice) => <option key={choice.value} value={choice.value}>{choice.label}</option>)}
    </select>
  );
}

function Suggest({ label, value, options, onChange, id }: {
  label: string; value: unknown; options: string[]; onChange: (v: string | null) => void; id: string;
}) {
  return (
    <>
      <input className="input input-sm mono" aria-label={label} list={id} value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value || null)} />
      <datalist id={id}>{options.map((option) => <option key={option} value={option} />)}</datalist>
    </>
  );
}

const plain = (values: string[]): Choice[] => values.map((value) => ({ value, label: value }));

/** One field of a trigger/condition/action, rendered from its schema kind. */
export function FieldInput({ field, value, siblings, onChange }: FieldInputProps) {
  const ctx = useRuleEditor();
  const label = field.label;
  const id = `field-${field.name}-${field.kind}`;
  if (NUMERIC.has(field.kind)) {
    return (
      <input className="input input-sm" type="number" aria-label={label} step={field.kind === "float" || field.kind === "percent" ? "any" : 1}
        value={typeof value === "number" ? value : ""}
        onChange={(event) => onChange(event.target.value === "" ? null : Number(event.target.value))} />
    );
  }
  switch (field.kind) {
    case "bool":
      return <input type="checkbox" aria-label={label} checked={value === true} onChange={(e) => onChange(e.target.checked)} />;
    case "string":
      return <input className="input input-sm mono" aria-label={label} value={typeof value === "string" ? value : ""}
        onChange={(event) => onChange(event.target.value || null)} />;
    case "value": case "pad": case "instance":
      return <ValueInput label={label} value={value as Value} onChange={onChange} />;
    case "op":
      return <Select label={label} value={value} choices={plain(ctx.schema.operators)} onChange={onChange} />;
    case "event":
      return <Suggest id={id} label={label} value={value} options={field.options ?? ctx.schema.events} onChange={onChange} />;
    case "flag":
      return <Select label={label} value={value} choices={plain(field.options ?? ctx.schema.flags)} onChange={onChange} />;
    case "node":
      return <Suggest id={id} label={label} value={value} options={ctx.nodes} onChange={onChange} />;
    case "property": {
      const node = typeof siblings.node === "string" ? siblings.node : "";
      return <Suggest id={id} label={label} value={value} options={ctx.properties(node)} onChange={onChange} />;
    }
    case "function":
      return <Select label={label} value={value} choices={plain(ctx.functions)} onChange={onChange} />;
    case "slot":
      return <Select label={label} value={value} choices={ctx.slots} onChange={onChange} />;
    case "probe":
      return <Select label={label} value={value} choices={ctx.probes} onChange={onChange} empty="this probe" />;
    case "level":
      return <Select label={label} value={value ?? "info"} choices={plain(["info", "warning", "error"])} onChange={onChange} />;
    case "direction":
      return <Select label={label} value={value ?? "downstream"} choices={plain(["downstream", "upstream"])} onChange={onChange} />;
    case "fields": case "args": case "params":
      return <KeyValueEditor label={label} value={value as Record<string, Value>} onChange={onChange} />;
    default:
      return <input className="input input-sm" aria-label={label} value={String(value ?? "")} onChange={(e) => onChange(e.target.value)} />;
  }
}
