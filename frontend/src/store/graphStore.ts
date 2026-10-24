// Graph being edited, with undo/redo history and a clipboard.

import { create } from "zustand";
import type { ApiFunction, ProbeRuleSet, Slot } from "../api/dynamic";
import type { Graph, GraphEdge, GraphNode, Position, ProbeScript, PropertyValue } from "../api/types";
import * as fns from "../lib/apiFunctions";
import * as ops from "../lib/graphOps";
import * as probes from "../lib/probeRules";
import * as scripts from "../lib/scripts";
import * as slots from "../lib/slots";

const HISTORY_LIMIT = 100;
const PASTE_OFFSET: Position = { x: 40, y: 40 };

/** An outer graph (project or parent component) suspended while editing an inner one. */
export interface SuspendedScope {
  graph: Graph;
  past: Graph[];
  future: Graph[];
}

interface GraphStore {
  graph: Graph;
  past: Graph[];
  future: Graph[];
  revision: number;
  clipboard: Graph | null;
  /** Outer graphs, innermost last; empty while editing the project itself. */
  scopes: SuspendedScope[];
  /** Edit ``graph`` (a component definition) keeping the current one for later. */
  enterScope: (graph: Graph) => void;
  /** Back to the outer graph; returns the inner graph that was being edited. */
  exitScope: () => Graph;
  load: (graph: Graph) => void;
  commit: (graph: Graph) => void;
  checkpoint: () => void;
  addNode: (factory: string, position: Position) => GraphNode;
  updateNode: (id: string, patch: Partial<GraphNode>) => void;
  renameNode: (id: string, name: string) => boolean;
  setProperty: (nodeId: string, name: string, value: PropertyValue | undefined) => void;
  setPadProperty: (nodeId: string, pad: string, name: string, value: PropertyValue | undefined) => void;
  moveNodes: (positions: Record<string, Position>) => void;
  addEdge: (edge: GraphEdge) => void;
  removeElements: (nodeIds: string[], edgeIds: string[]) => void;
  addScript: (script: ProbeScript) => void;
  updateScript: (id: string, patch: Partial<Omit<ProbeScript, "id">>) => void;
  removeScript: (id: string) => void;
  addProbe: (probe: ProbeRuleSet) => void;
  updateProbe: (id: string, patch: Partial<Omit<ProbeRuleSet, "id">>) => void;
  removeProbe: (id: string) => void;
  addSlot: (slot: Slot) => void;
  updateSlot: (id: string, patch: Partial<Omit<Slot, "id">>) => void;
  removeSlot: (id: string) => void;
  addFunction: (fn: ApiFunction) => void;
  updateFunction: (name: string, fn: ApiFunction) => void;
  removeFunction: (name: string) => void;
  undo: () => void;
  redo: () => void;
  copy: (nodeIds: string[]) => void;
  paste: () => string[];
}

export const useGraphStore = create<GraphStore>((set, get) => {
  /** Replace the graph, recording the previous one for undo. */
  const commit = (graph: Graph) =>
    set((state) => ({
      graph,
      past: [...state.past, state.graph].slice(-HISTORY_LIMIT),
      future: [],
      revision: state.revision + 1,
    }));

  return {
    graph: ops.EMPTY_GRAPH,
    past: [],
    future: [],
    revision: 0,
    clipboard: null,
    scopes: [],
    enterScope: (graph) =>
      set((state) => ({
        scopes: [...state.scopes, { graph: state.graph, past: state.past, future: state.future }],
        graph, past: [], future: [], revision: state.revision + 1,
      })),
    exitScope: () => {
      const { graph, scopes } = get();
      const outer = scopes[scopes.length - 1];
      if (!outer) return graph;
      set((state) => ({ ...outer, scopes: state.scopes.slice(0, -1), revision: state.revision + 1 }));
      return graph;
    },
    load: (graph) => set((state) => ({ graph, past: [], future: [], revision: state.revision + 1 })),
    commit,
    checkpoint: () =>
      set((state) => ({ past: [...state.past, state.graph].slice(-HISTORY_LIMIT), future: [] })),
    addNode: (factory, position) => {
      const node = ops.createNode(get().graph, factory, position);
      commit(ops.addNode(get().graph, node));
      return node;
    },
    updateNode: (id, patch) => commit(ops.updateNode(get().graph, id, patch)),
    renameNode: (id, name) => {
      const graph = ops.renameNode(get().graph, id, name);
      if (graph) commit(graph);
      return graph !== null;
    },
    setProperty: (nodeId, name, value) => commit(ops.setProperty(get().graph, nodeId, name, value)),
    setPadProperty: (nodeId, pad, name, value) =>
      commit(ops.setPadProperty(get().graph, nodeId, pad, name, value)),
    moveNodes: (positions) =>
      set((state) => ({ graph: ops.moveNodes(state.graph, positions), revision: state.revision + 1 })),
    addEdge: (edge) => commit(ops.addEdge(get().graph, edge)),
    removeElements: (nodeIds, edgeIds) => {
      if (nodeIds.length === 0 && edgeIds.length === 0) return;
      commit(ops.removeElements(get().graph, nodeIds, edgeIds));
    },
    addScript: (script) => commit(scripts.addScript(get().graph, script)),
    updateScript: (id, patch) => commit(scripts.updateScript(get().graph, id, patch)),
    removeScript: (id) => commit(scripts.removeScript(get().graph, id)),
    addProbe: (probe) => commit(probes.addProbe(get().graph, probe)),
    updateProbe: (id, patch) => commit(probes.updateProbe(get().graph, id, patch)),
    removeProbe: (id) => commit(probes.removeProbe(get().graph, id)),
    addSlot: (slot) => commit(slots.addSlot(get().graph, slot)),
    updateSlot: (id, patch) => commit(slots.updateSlot(get().graph, id, patch)),
    removeSlot: (id) => commit(slots.removeSlot(get().graph, id)),
    addFunction: (fn) => commit(fns.addFunction(get().graph, fn)),
    updateFunction: (name, fn) => commit(fns.updateFunction(get().graph, name, fn)),
    removeFunction: (name) => commit(fns.removeFunction(get().graph, name)),
    undo: () =>
      set((state) => {
        const previous = state.past[state.past.length - 1];
        if (!previous) return state;
        return {
          graph: previous,
          past: state.past.slice(0, -1),
          future: [state.graph, ...state.future],
          revision: state.revision + 1,
        };
      }),
    redo: () =>
      set((state) => {
        const next = state.future[0];
        if (!next) return state;
        return {
          graph: next,
          past: [...state.past, state.graph],
          future: state.future.slice(1),
          revision: state.revision + 1,
        };
      }),
    copy: (nodeIds) => {
      if (nodeIds.length > 0) set({ clipboard: ops.extractSubgraph(get().graph, nodeIds) });
    },
    paste: () => {
      const clip = get().clipboard;
      if (!clip || clip.nodes.length === 0) return [];
      const result = ops.pasteSubgraph(get().graph, clip, PASTE_OFFSET);
      commit(result.graph);
      set({
        clipboard: {
          ...clip,
          nodes: clip.nodes.map((n) => ({
            ...n,
            position: { x: n.position.x + PASTE_OFFSET.x, y: n.position.y + PASTE_OFFSET.y },
          })),
        },
      });
      return result.nodeIds;
    },
  };
});

/** The project's graph, even while a component definition is open on the canvas. */
export function projectGraph(state: Pick<GraphStore, "graph" | "scopes"> = useGraphStore.getState()): Graph {
  return state.scopes[0]?.graph ?? state.graph;
}
