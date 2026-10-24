// Applies React Flow "select" changes to a list of selected ids.

interface SelectChangeLike {
  type: string;
  id?: string;
  selected?: boolean;
}

export function applySelection(current: string[], changes: SelectChangeLike[]): string[] {
  const selects = changes.filter((change) => change.type === "select" && change.id);
  const removed = changes.filter((change) => change.type === "remove" && change.id).map((change) => change.id);
  if (selects.length === 0 && removed.length === 0) return current;
  const next = new Set(current);
  for (const change of selects) {
    if (change.selected) next.add(change.id as string);
    else next.delete(change.id as string);
  }
  for (const id of removed) next.delete(id as string);
  const result = [...next];
  const same = result.length === current.length && result.every((id) => current.includes(id));
  return same ? current : result;
}
