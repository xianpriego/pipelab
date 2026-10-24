import { useEffect, useState } from "react";
import { formatPropertyValue, parsePropertyInput } from "../../../lib/propertyValues";
import type { FieldProps } from "./types";

const MULTILINE = new Set(["caps", "structure", "array", "boxed"]);

export function TextField({ prop, value, onCommit, disabled }: FieldProps) {
  const [text, setText] = useState(formatPropertyValue(value));
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setText(formatPropertyValue(value));
    setError(null);
  }, [value]);

  const commit = () => {
    if (text === formatPropertyValue(value)) return;
    const result = parsePropertyInput(prop, text);
    if (result.ok) onCommit(result.value);
    else setError(result.error);
  };

  const common = {
    value: text,
    disabled,
    "aria-label": prop.name,
    placeholder: formatPropertyValue(prop.default) || (prop.type === "fraction" ? "30/1" : ""),
    onChange: (event: { target: { value: string } }) => {
      setText(event.target.value);
      setError(null);
    },
    onBlur: commit,
  };
  return (
    <>
      {MULTILINE.has(prop.type) ? (
        <textarea className={`textarea${error ? " invalid" : ""}`} rows={2} {...common}
          onKeyDown={(event) => event.key === "Enter" && (event.ctrlKey || event.metaKey) && commit()} />
      ) : (
        <input className={`input${prop.type === "fraction" ? " mono" : ""}${error ? " invalid" : ""}`} {...common}
          onKeyDown={(event) => event.key === "Enter" && commit()} />
      )}
      {error ? <div className="prop-error">{error}</div> : null}
    </>
  );
}
