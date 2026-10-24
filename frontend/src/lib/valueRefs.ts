// "$name" references in probe/function values: parsing, formatting and autocomplete.

import type { Value } from "../api/dynamic";

/** A string referencing a variable, builtin or argument ("$$x" is the literal "$x"). */
export function isReference(value: Value | undefined): value is string {
  return typeof value === "string" && value.startsWith("$") && !value.startsWith("$$") && value.length > 1;
}

export function referenceName(value: string): string {
  return value.slice(1);
}

/** Text typed in a value box → Value: "" → null, true/false → bool, numbers → number, else text. */
export function parseValue(text: string): Value {
  const trimmed = text.trim();
  if (!trimmed) return null;
  if (trimmed.startsWith("$")) return trimmed;
  if (trimmed === "true" || trimmed === "false") return trimmed === "true";
  if (/^-?\d+(\.\d+)?([eE][-+]?\d+)?$/.test(trimmed)) return Number(trimmed);
  return text;
}

export function formatValue(value: Value | undefined): string {
  if (value === null || value === undefined) return "";
  return String(value);
}

export interface Suggestion {
  /** "$name" */
  text: string;
  description: string;
  kind: "variable" | "builtin" | "param";
}

export interface ReferenceScope {
  variables?: string[];
  builtins?: { name: string; description: string }[];
  params?: string[];
}

export function referenceSuggestions(scope: ReferenceScope): Suggestion[] {
  return [
    ...(scope.variables ?? []).map((name) => ({ text: `$${name}`, description: "probe variable", kind: "variable" as const })),
    ...(scope.params ?? []).map((name) => ({ text: `$${name}`, description: "function argument", kind: "param" as const })),
    // The schema names builtins with their "$" ("$value"); accept bare names too.
    ...(scope.builtins ?? []).map((b) => ({
      text: b.name.startsWith("$") ? b.name : `$${b.name}`, description: b.description, kind: "builtin" as const,
    })),
  ];
}

/** Suggestions matching what is being typed (only once it starts with "$"). */
export function matchSuggestions(text: string, suggestions: Suggestion[]): Suggestion[] {
  if (!text.startsWith("$") || text.startsWith("$$")) return [];
  const needle = text.toLowerCase();
  return suggestions.filter((s) => s.text.toLowerCase().startsWith(needle) && s.text !== text);
}

/** References used in a value that are not known in the scope (shown as warnings). */
export function unknownReference(value: Value | undefined, scope: ReferenceScope): string | null {
  if (!isReference(value)) return null;
  const known = new Set(referenceSuggestions(scope).map((s) => s.text));
  return known.has(value) ? null : value;
}
