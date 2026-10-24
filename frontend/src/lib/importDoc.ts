// Recognises Pipelab JSON documents (export format, project, or bare graph).

import type { Graph } from "../api/types";

export interface ImportedDoc {
  name: string | null;
  graph: Graph;
}

function isGraph(value: unknown): value is Graph {
  return (
    typeof value === "object" && value !== null &&
    Array.isArray((value as Graph).nodes) && Array.isArray((value as Graph).edges)
  );
}

export function parsePipelabJson(text: string): ImportedDoc {
  let data: unknown;
  try {
    data = JSON.parse(text);
  } catch {
    throw new Error("The file is not valid JSON.");
  }
  if (isGraph(data)) return { name: null, graph: data };
  if (typeof data === "object" && data !== null && isGraph((data as { graph?: unknown }).graph)) {
    const name = (data as { name?: unknown }).name;
    return { name: typeof name === "string" ? name : null, graph: (data as { graph: Graph }).graph };
  }
  throw new Error("No Pipelab graph found in this file.");
}

/** Strip the shell prefix so a copied command line can be pasted as-is. */
export function cleanLaunchLine(text: string): string {
  return text.replace(/\\\r?\n/g, " ").trim();
}
