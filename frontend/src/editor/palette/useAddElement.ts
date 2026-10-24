import { useReactFlow } from "@xyflow/react";
import { useCallback } from "react";
import { freePosition } from "../../lib/graphOps";
import { useGraphStore } from "../../store/graphStore";
import { useUiStore } from "../../store/uiStore";

/** Adds an element at the centre of the visible canvas and selects it. */
export function useAddElement(): (factory: string) => void {
  const flow = useReactFlow();
  return useCallback(
    (factory: string) => {
      const pane = document.querySelector(".canvas")?.getBoundingClientRect();
      const center = pane
        ? flow.screenToFlowPosition({ x: pane.left + pane.width / 2, y: pane.top + pane.height / 2 })
        : { x: 0, y: 0 };
      const store = useGraphStore.getState();
      const position = freePosition(store.graph, { x: center.x - 90, y: center.y - 40 });
      const node = store.addNode(factory, position);
      useUiStore.getState().select([node.id], []);
    },
    [flow],
  );
}
