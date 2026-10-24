// Parsing and formatting of property values per GObject property type.

import type { PropertyInfo, PropertyValue } from "../api/types";

export const INTEGER_TYPES = new Set(["int", "uint", "int64", "uint64"]);
export const NUMBER_TYPES = new Set([...INTEGER_TYPES, "float", "double"]);

export type ParseResult = { ok: true; value: PropertyValue } | { ok: false; error: string };

const ok = (value: PropertyValue): ParseResult => ({ ok: true, value });
const fail = (error: string): ParseResult => ({ ok: false, error });

function parseNumber(prop: PropertyInfo, raw: string): ParseResult {
  const text = raw.trim();
  if (text === "") return fail("A number is required");
  const value = Number(text);
  if (!Number.isFinite(value)) return fail("Not a number");
  if (INTEGER_TYPES.has(prop.type) && !Number.isInteger(value)) return fail("Must be an integer");
  if (prop.minimum !== null && value < prop.minimum) return fail(`Minimum is ${prop.minimum}`);
  if (prop.maximum !== null && value > prop.maximum) return fail(`Maximum is ${prop.maximum}`);
  return ok(value);
}

/** Convert user input (text or checkbox) to the stored JSON value. */
export function parsePropertyInput(prop: PropertyInfo, raw: string | boolean): ParseResult {
  if (prop.type === "boolean") {
    if (typeof raw === "boolean") return ok(raw);
    const text = raw.trim().toLowerCase();
    if (["true", "1", "yes"].includes(text)) return ok(true);
    if (["false", "0", "no"].includes(text)) return ok(false);
    return fail("Expected true or false");
  }
  const text = String(raw);
  if (NUMBER_TYPES.has(prop.type)) return parseNumber(prop, text);
  if (prop.type === "enum") {
    const match = prop.enum_values.find((v) => v.nick === text || v.name === text || String(v.value) === text);
    return match ? ok(match.nick) : fail("Unknown value");
  }
  if (prop.type === "fraction") {
    return /^\s*-?\d+\s*\/\s*\d+\s*$/.test(text) ? ok(text.replace(/\s+/g, "")) : fail("Use num/den, e.g. 30/1");
  }
  return ok(text);
}

export function formatPropertyValue(value: PropertyValue | null | undefined): string {
  if (value === null || value === undefined) return "";
  if (typeof value === "boolean") return value ? "true" : "false";
  return String(value);
}

export function splitFlags(value: PropertyValue | null | undefined): string[] {
  if (value === null || value === undefined || typeof value !== "string") return [];
  return value.split("+").map((flag) => flag.trim()).filter((flag) => flag && flag !== "0");
}

export function joinFlags(flags: string[]): string {
  return flags.length > 0 ? flags.join("+") : "0";
}

/** Writable now while the pipeline runs (per GStreamer param flags). */
export function isLiveEditable(prop: PropertyInfo): boolean {
  if (!prop.writable || prop.construct_only) return false;
  return prop.mutable === "playing" || prop.controllable || prop.type === "pad";
}

/** Numeric range small enough to be edited with a slider. */
export function sliderRange(prop: PropertyInfo): [number, number] | null {
  if (!NUMBER_TYPES.has(prop.type) || prop.minimum === null || prop.maximum === null) return null;
  const span = prop.maximum - prop.minimum;
  return span > 0 && span <= 100_000 ? [prop.minimum, prop.maximum] : null;
}

export function sliderStep(prop: PropertyInfo, range: [number, number]): number {
  if (INTEGER_TYPES.has(prop.type)) return 1;
  const span = range[1] - range[0];
  return span <= 2 ? 0.01 : span <= 20 ? 0.1 : 1;
}
