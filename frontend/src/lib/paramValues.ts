// Component parameter values typed in a text box.

import type { Value } from "../api/components";

/** "" → null, true/false → bool, numbers → number, anything else stays text. */
export function parseValue(text: string): Value {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (trimmed === "true" || trimmed === "false") return trimmed === "true";
  if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(trimmed)) return Number(trimmed);
  return text;
}

export function formatValue(value: Value | undefined): string {
  if (value === null || value === undefined) return "";
  return String(value);
}
