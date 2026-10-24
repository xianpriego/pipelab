// Commands on the canvas selection, which mixes elements, links and slot nodes.

import { useGraphStore } from "../store/graphStore";
import { useUiStore } from "../store/uiStore";
import { slotIdOf } from "./slots/slotFlow";

/** Removes selected elements, links and slots together. */
export function deleteSelection(nodes: string[], edges: string[]): void {
  const graphs = useGraphStore.getState();
  const slots = nodes.map(slotIdOf).filter((id): id is string => id !== null);
  const elements = nodes.filter((id) => slotIdOf(id) === null);
  if (elements.length || edges.length) graphs.removeElements(elements, edges);
  for (const slot of slots) graphs.removeSlot(slot);
  useUiStore.getState().select([], []);
}
