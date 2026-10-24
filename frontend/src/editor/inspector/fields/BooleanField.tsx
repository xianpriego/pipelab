import type { FieldProps } from "./types";

export function BooleanField({ prop, value, onCommit, disabled }: FieldProps) {
  const checked = Boolean(value ?? prop.default);
  return (
    <label className="switch" title={checked ? "true" : "false"}>
      <input type="checkbox" checked={checked} disabled={disabled} aria-label={prop.name}
        onChange={(event) => onCommit(event.target.checked)} />
      <span />
    </label>
  );
}
