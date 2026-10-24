import type { Spec } from "../../api/dynamic";
import { FieldInput } from "./FieldInput";

interface SpecFormProps<T extends { type: string }> {
  /** All the choices (triggers, conditions or actions). */
  specs: Spec[];
  item: T;
  onChange: (item: T) => void;
  /** Accessible name of the type select ("Trigger", "Condition 1"…). */
  label: string;
}

/** A type select plus the fields of the chosen type, generated from the schema. */
export function SpecForm<T extends { type: string }>({ specs, item, onChange, label }: SpecFormProps<T>) {
  const spec = specs.find((candidate) => candidate.type === item.type);
  const record = item as unknown as Record<string, unknown>;
  return (
    <div className="spec-form">
      <select className="select select-sm spec-type" aria-label={label} value={item.type} title={spec?.description}
        onChange={(event) => onChange({ type: event.target.value } as T)}>
        {specs.map((candidate) => <option key={candidate.type} value={candidate.type}>{candidate.label}</option>)}
      </select>
      {spec?.fields.map((field) => (
        <label key={field.name} className={`spec-field kind-${field.kind}`}>
          <span className="spec-field-label">{field.label}{field.required ? " *" : ""}</span>
          <FieldInput field={field} value={record[field.name]} siblings={record}
            onChange={(value) => onChange({ ...item, [field.name]: value } as T)} />
        </label>
      ))}
    </div>
  );
}
