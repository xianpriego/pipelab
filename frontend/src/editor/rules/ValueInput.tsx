import { useMemo, useState } from "react";
import type { Value } from "../../api/dynamic";
import { formatValue, matchSuggestions, parseValue, referenceSuggestions, unknownReference } from "../../lib/valueRefs";
import { useRuleEditor } from "./editorContext";

interface ValueInputProps {
  value: Value | undefined;
  onChange: (value: Value) => void;
  label: string;
  placeholder?: string;
}

/** Literal value or "$reference" with autocomplete of variables, builtins and arguments. */
export function ValueInput({ value, onChange, label, placeholder }: ValueInputProps) {
  const ctx = useRuleEditor();
  const [text, setText] = useState(formatValue(value));
  const [focused, setFocused] = useState(false);
  const scope = useMemo(
    () => ({ variables: ctx.variables, params: ctx.params, builtins: ctx.schema.builtins }),
    [ctx.variables, ctx.params, ctx.schema.builtins],
  );
  const suggestions = useMemo(() => referenceSuggestions(scope), [scope]);
  const matches = focused ? matchSuggestions(text, suggestions).slice(0, 8) : [];
  const unknown = unknownReference(value, scope);

  const commit = (next: string) => {
    setText(next);
    onChange(parseValue(next));
  };

  return (
    <span className="value-input">
      <input className="input input-sm mono" value={text} aria-label={label} placeholder={placeholder ?? "value or $ref"}
        onChange={(event) => commit(event.target.value)} onFocus={() => setFocused(true)}
        onBlur={() => setTimeout(() => setFocused(false), 120)} />
      {matches.length ? (
        <ul className="ref-suggestions" role="listbox" aria-label={`${label} suggestions`}>
          {matches.map((s) => (
            <li key={s.text}>
              <button type="button" role="option" aria-selected={false} onMouseDown={(e) => e.preventDefault()}
                onClick={() => commit(s.text)}>
                <span className={`mono ref-${s.kind}`}>{s.text}</span>
                <span className="faint">{s.description}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {unknown && !focused ? <span className="badge warning" title="Not a known variable, builtin or argument">?</span> : null}
    </span>
  );
}
