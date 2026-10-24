import type { FieldProps } from "./types";

interface PadFieldProps extends FieldProps {
  pads: string[];
}

export function PadField({ prop, value, onCommit, disabled, pads }: PadFieldProps) {
  const current = typeof value === "string" ? value : "";
  const options = current && !pads.includes(current) ? [current, ...pads] : pads;
  return (
    <select className="select" value={current} disabled={disabled} aria-label={prop.name}
      onChange={(event) => event.target.value && onCommit(event.target.value)}>
      <option value="">{pads.length ? "(default)" : "(link pads first)"}</option>
      {options.map((pad) => (
        <option key={pad} value={pad}>
          {pad}
        </option>
      ))}
    </select>
  );
}
