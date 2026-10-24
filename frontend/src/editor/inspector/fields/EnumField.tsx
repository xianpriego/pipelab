import type { FieldProps } from "./types";

export function EnumField({ prop, value, onCommit, disabled }: FieldProps) {
  const current = String(value ?? prop.default ?? "");
  return (
    <select className="select" value={current} disabled={disabled} aria-label={prop.name}
      onChange={(event) => onCommit(event.target.value)}>
      {prop.enum_values.map((option) => (
        <option key={option.nick} value={option.nick} title={option.name}>
          {option.nick} ({option.value}){option.name && option.name !== option.nick ? ` — ${option.name}` : ""}
        </option>
      ))}
    </select>
  );
}
