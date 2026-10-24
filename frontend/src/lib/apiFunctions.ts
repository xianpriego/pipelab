// Pipeline API functions (docs/DYNAMIC.md §3): graph operations and argument typing.

import type { ApiFunction, FunctionParam, ParamType, Value } from "../api/dynamic";
import type { Graph } from "../api/types";

export function functionsOf(graph: Graph): ApiFunction[] {
  return graph.functions ?? [];
}

export function addFunction(graph: Graph, fn: ApiFunction): Graph {
  return { ...graph, functions: [...functionsOf(graph), fn] };
}

export function updateFunction(graph: Graph, name: string, fn: ApiFunction): Graph {
  return { ...graph, functions: functionsOf(graph).map((current) => (current.name === name ? fn : current)) };
}

export function removeFunction(graph: Graph, name: string): Graph {
  return { ...graph, functions: functionsOf(graph).filter((fn) => fn.name !== name) };
}

const IDENTIFIER = /^[a-z_][a-z0-9_]*$/;

export function isIdentifier(name: string): boolean {
  return IDENTIFIER.test(name);
}

export function createFunction(taken: string[]): ApiFunction {
  let index = 1;
  while (taken.includes(`my_function${index === 1 ? "" : index}`)) index += 1;
  return { name: `my_function${index === 1 ? "" : index}`, description: "", params: [], actions: [] };
}

/** Text typed in a call form → argument of the declared type (null when empty). */
export function typedArg(type: ParamType, text: string): Value {
  const trimmed = text.trim();
  if (type === "bool") return trimmed === "true" || trimmed === "1" || trimmed === "on";
  if (!trimmed) return null;
  if (type === "int") {
    const value = Number.parseInt(trimmed, 10);
    return Number.isFinite(value) ? value : null;
  }
  if (type === "float") {
    const value = Number.parseFloat(trimmed);
    return Number.isFinite(value) ? value : null;
  }
  return text;
}

/** Arguments of a call: typed values, defaults for untouched fields, nothing for empty optional ones. */
export function callArgs(params: FunctionParam[], texts: Record<string, string>): Record<string, Value> {
  const args: Record<string, Value> = {};
  for (const param of params) {
    const text = texts[param.name];
    if (text === undefined) {
      if (param.default !== undefined && param.default !== null) args[param.name] = param.default;
      continue;
    }
    const value = typedArg(param.type, text);
    if (value !== null) args[param.name] = value;
  }
  return args;
}

/** Python-ish signature: ``add_input(location: str, latency: int = 2000)``. */
export function signature(name: string, params: FunctionParam[], returns = ""): string {
  const types: Record<ParamType, string> = { string: "str", int: "int", float: "float", bool: "bool" };
  const args = params.map((p) => {
    const base = `${p.name}: ${types[p.type]}`;
    return p.default === undefined || p.default === null ? base : `${base} = ${JSON.stringify(p.default)}`;
  });
  return `${name}(${args.join(", ")})${returns ? ` -> ${returns}` : ""}`;
}
