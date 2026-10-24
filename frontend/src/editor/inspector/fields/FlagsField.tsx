import { joinFlags, splitFlags } from "../../../lib/propertyValues";
import type { FieldProps } from "./types";

export function FlagsField({ prop, value, onCommit, disabled }: FieldProps) {
  const active = new Set(splitFlags(value ?? prop.default));
  const toggle = (nick: string) => {
    const next = new Set(active);
    if (next.has(nick)) next.delete(nick);
    else next.add(nick);
    onCommit(joinFlags(prop.enum_values.map((v) => v.nick).filter((n) => next.has(n))));
  };
  return (
    <div className="flags-field">
      {prop.enum_values.map((option) => (
        <label key={option.nick} className="flag-option" title={option.name}>
          <input type="checkbox" checked={active.has(option.nick)} disabled={disabled}
            onChange={() => toggle(option.nick)} />
          {option.nick}
        </label>
      ))}
    </div>
  );
}
