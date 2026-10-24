// Quick client-side compatibility hint between two pads (the backend decides).

const BASE = /^([^()]+)/;

export function baseMediaType(mediaType: string): string {
  const match = BASE.exec(mediaType);
  return match ? match[1] : mediaType;
}

export type CompatHint = "compatible" | "convertible" | "unknown";

/** Media types overlap → compatible; otherwise a converter may be suggested. */
export function compatHint(sourceTypes: string[], targetTypes: string[]): CompatHint {
  if (sourceTypes.length === 0 || targetTypes.length === 0) return "unknown";
  if (sourceTypes.includes("ANY") || targetTypes.includes("ANY")) return "compatible";
  const targets = new Set(targetTypes.map(baseMediaType));
  return sourceTypes.some((type) => targets.has(baseMediaType(type))) ? "compatible" : "convertible";
}
