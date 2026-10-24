// Identifier and element-name helpers.

let counter = 0;

export function newId(prefix: string): string {
  counter += 1;
  const random = Math.random().toString(36).slice(2, 8);
  return `${prefix}${Date.now().toString(36)}${counter.toString(36)}${random}`;
}

/** GStreamer-style unique name: `<base><n>` with the smallest free n. */
export function uniqueName(base: string, taken: Iterable<string>): string {
  const used = new Set(taken);
  const stem = base.replace(/\d+$/, "") || "element";
  for (let index = 0; ; index += 1) {
    const candidate = `${stem}${index}`;
    if (!used.has(candidate)) return candidate;
  }
}

/** Valid GStreamer object name characters. */
export function sanitizeName(name: string): string {
  return name.trim().replace(/[^A-Za-z0-9_\-.:]/g, "_");
}
