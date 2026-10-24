// Commands on the canvas selection.

import { useGraphStore } from "../store/graphStore";
import { useUiStore } from "../store/uiStore";

/** Removes the selected elements and links (and the links of removed elements). */
export function deleteSelection(nodes: string[], edges: string[]): void {
  useGraphStore.getState().removeElements(nodes, edges);
  useUiStore.getState().select([], []);
}
