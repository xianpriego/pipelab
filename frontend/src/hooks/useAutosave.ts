import { useEffect, useRef } from "react";
import { saveProject } from "../editor/actions";
import type { Graph } from "../api/types";
import { projectGraph, useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";

const DEBOUNCE_MS = 800;

/**
 * Saves the project shortly after any change of its graph or metadata. While a component is open
 * the project graph is suspended (unchanged): component edits are saved to the library explicitly.
 */
export function useAutosave(loaded: boolean): void {
  const graph = useGraphStore((state) => projectGraph(state));
  const metaRevision = useProjectStore((state) => state.metaRevision);
  const baseline = useRef<{ graph: Graph; meta: number } | null>(null);

  useEffect(() => {
    const key = { graph, meta: metaRevision };
    if (!loaded) return undefined;
    if (baseline.current === null) {
      baseline.current = key;
      return undefined;
    }
    if (baseline.current.graph === graph && baseline.current.meta === metaRevision) return undefined;
    useProjectStore.getState().setSaveState("dirty");
    const timer = setTimeout(() => {
      baseline.current = key;
      void saveProject();
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [graph, metaRevision, loaded]);

  useEffect(() => {
    const onUnload = (event: BeforeUnloadEvent) => {
      if (useProjectStore.getState().saveState === "dirty") event.preventDefault();
    };
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, []);
}
