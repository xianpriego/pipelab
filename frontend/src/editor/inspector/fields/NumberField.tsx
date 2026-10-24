import { useEffect, useState } from "react";
import { formatPropertyValue, parsePropertyInput, sliderRange, sliderStep } from "../../../lib/propertyValues";
import type { FieldProps } from "./types";

export function NumberField({ prop, value, onCommit, disabled }: FieldProps) {
  const [text, setText] = useState(formatPropertyValue(value));
  const [error, setError] = useState<string | null>(null);
  const range = sliderRange(prop);

  useEffect(() => {
    setText(formatPropertyValue(value));
    setError(null);
  }, [value]);

  const commit = (raw: string) => {
    if (raw.trim() === "" || raw === formatPropertyValue(value)) return;
    const result = parsePropertyInput(prop, raw);
    if (result.ok) onCommit(result.value);
    else setError(result.error);
  };

  const current = Number(value ?? prop.default ?? range?.[0] ?? 0);
  return (
    <div className="number-field">
      {range ? (
        <input type="range" min={range[0]} max={range[1]} step={sliderStep(prop, range)} value={current}
          disabled={disabled} aria-label={`${prop.name} slider`}
          onChange={(event) => onCommit(Number(event.target.value))} />
      ) : null}
      <input
        className={`input mono${error ? " invalid" : ""}`}
        value={text}
        placeholder={formatPropertyValue(prop.default)}
        disabled={disabled}
        aria-label={prop.name}
        title={error ?? `${prop.minimum ?? "−∞"} … ${prop.maximum ?? "∞"}`}
        onChange={(event) => {
          setText(event.target.value);
          setError(null);
        }}
        onBlur={(event) => commit(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && commit((event.target as HTMLInputElement).value)}
      />
      {error ? <div className="prop-error">{error}</div> : null}
    </div>
  );
}
