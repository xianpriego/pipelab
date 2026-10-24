// Runtime ids inside component instances are prefixed: "<instance node id>/<inner id>".

/** Prefix of runtime ids for the scope reached through ``path`` (instance node ids). */
export function scopePrefix(path: string[]): string {
  return path.length ? `${path.join("/")}/` : "";
}

/** Entries of ``record`` belonging to the scope, keyed by the inner id (deeper scopes excluded). */
export function scoped<T>(record: Record<string, T>, prefix: string): Record<string, T> {
  if (!prefix) return record;
  const result: Record<string, T> = {};
  for (const [key, value] of Object.entries(record)) {
    if (!key.startsWith(prefix)) continue;
    const inner = key.slice(prefix.length);
    if (inner && !inner.includes("/")) result[inner] = value;
  }
  return result;
}

/** Inner id of a runtime id in the scope, or null when it belongs elsewhere. */
export function scopedId(id: string | null | undefined, prefix: string): string | null {
  if (!id) return null;
  if (!prefix) return id.includes("/") ? null : id;
  if (!id.startsWith(prefix)) return null;
  const inner = id.slice(prefix.length);
  return inner && !inner.includes("/") ? inner : null;
}
