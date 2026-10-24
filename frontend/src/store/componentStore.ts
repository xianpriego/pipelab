// Component library and the component definitions being edited (a stack: nested components).

import { create } from "zustand";
import { api, errorMessage } from "../api/client";
import type { ComponentDef, ComponentParam, ComponentPort } from "../api/dynamic";
import type { Graph } from "../api/types";
import { pruneDefinition } from "../lib/components";
import { scopePrefix } from "../lib/scope";
import { useCatalogStore } from "./catalogStore";
import { useGraphStore } from "./graphStore";
import { notify } from "./uiStore";

export interface ComponentSession {
  /** Definition as last loaded/saved. */
  base: ComponentDef;
  /** Instance node ids leading here (runtime id prefix); empty when opened from the library. */
  path: string[];
  name: string;
  description: string;
  ports: ComponentPort[];
  parameters: ComponentParam[];
  /** ``graphKey`` of the graph as last saved/loaded: any other graph makes the session dirty. */
  savedKey: string;
  metaDirty: boolean;
}

interface ComponentStore {
  library: ComponentDef[];
  libraryState: "idle" | "loading" | "ready" | "error";
  sessions: ComponentSession[];
  loadLibrary: () => Promise<ComponentDef[]>;
  /** Opens ``id`` for editing; ``path`` = instance node ids from the project (for runtime data). */
  enter: (id: string, path?: string[]) => Promise<boolean>;
  /** Leaves the innermost component (unsaved edits are lost: confirm before). */
  exit: () => void;
  /** Leaves components until ``depth`` sessions remain. */
  exitTo: (depth: number) => void;
  save: () => Promise<boolean>;
  discard: () => void;
  update: (patch: Partial<Pick<ComponentSession, "name" | "description" | "ports" | "parameters">>) => void;
}

export function graphKey(graph: Graph): string {
  return JSON.stringify(graph);
}

export function isDirty(session: ComponentSession, graph: Graph): boolean {
  return session.metaDirty || graphKey(graph) !== session.savedKey;
}

/** The definition as edited: session metadata + the given graph (stale ports/targets pruned). */
export function draftDefinition(session: ComponentSession, graph: Graph): ComponentDef {
  const draft: ComponentDef = {
    ...session.base, name: session.name, description: session.description, graph,
    ports: session.ports, parameters: session.parameters,
  };
  return { ...draft, ...pruneDefinition(draft, graph) };
}

/** Graph of the ``index``-th open component: on the canvas for the innermost, suspended otherwise. */
export function sessionGraph(index: number, sessions: ComponentSession[] = useComponentStore.getState().sessions): Graph {
  const graphs = useGraphStore.getState();
  return index === sessions.length - 1 ? graphs.graph : graphs.scopes[index + 1]?.graph ?? graphs.graph;
}

/** Whether any open component has unsaved changes. */
export function anyDirty(sessions: ComponentSession[] = useComponentStore.getState().sessions): boolean {
  return sessions.some((session, index) => isDirty(session, sessionGraph(index, sessions)));
}

/**
 * Prefix of runtime ids for what the canvas shows: "" for the project, "<instance>/" inside an
 * instance, null for a component opened from the library (no runtime data applies).
 */
export function runtimePrefix(sessions: ComponentSession[]): string | null {
  const top = current(sessions);
  if (!top) return "";
  return top.path.length ? scopePrefix(top.path) : null;
}

function current(sessions: ComponentSession[]): ComponentSession | undefined {
  return sessions[sessions.length - 1];
}

export const useComponentStore = create<ComponentStore>((set, get) => {
  const replaceCurrent = (patch: Partial<ComponentSession>) =>
    set((state) => {
      const top = current(state.sessions);
      return top ? { sessions: [...state.sessions.slice(0, -1), { ...top, ...patch }] } : state;
    });

  return {
    library: [],
    libraryState: "idle",
    sessions: [],

    loadLibrary: async () => {
      set({ libraryState: "loading" });
      try {
        const library = await api.listComponents();
        set({ library, libraryState: "ready" });
        return library;
      } catch {
        set({ libraryState: "error" });
        return get().library;
      }
    },

    enter: async (id, path = []) => {
      let def: ComponentDef;
      try {
        def = await api.getComponent(id);
      } catch (error) {
        notify({ level: "error", title: `Cannot open component "${id}"`, message: errorMessage(error) });
        return false;
      }
      const graphs = useGraphStore.getState();
      graphs.enterScope(def.graph);
      set((state) => ({
        sessions: [...state.sessions, {
          base: def, path, name: def.name, description: def.description, ports: def.ports,
          parameters: def.parameters, savedKey: graphKey(def.graph), metaDirty: false,
        }],
      }));
      return true;
    },

    exit: () => {
      if (!current(get().sessions)) return;
      useGraphStore.getState().exitScope();
      set((state) => ({ sessions: state.sessions.slice(0, -1) }));
    },

    exitTo: (depth) => {
      while (get().sessions.length > depth) get().exit();
    },

    save: async () => {
      const session = current(get().sessions);
      if (!session) return false;
      const graph = useGraphStore.getState().graph;
      try {
        const saved = await api.saveComponent(draftDefinition(session, graph));
        replaceCurrent({
          base: saved, ports: saved.ports, parameters: saved.parameters, name: saved.name,
          description: saved.description, savedKey: graphKey(graph), metaDirty: false,
        });
        void get().loadLibrary();
        void useCatalogStore.getState().refresh();
        notify({ level: "success", title: `Saved component "${saved.name}" (v${saved.version})`, timeout: 2500 });
        return true;
      } catch (error) {
        notify({ level: "error", title: "Could not save the component", message: errorMessage(error) });
        return false;
      }
    },

    discard: () => {
      const session = current(get().sessions);
      if (!session) return;
      useGraphStore.getState().load(session.base.graph);
      replaceCurrent({
        name: session.base.name, description: session.base.description, ports: session.base.ports,
        parameters: session.base.parameters, savedKey: graphKey(session.base.graph), metaDirty: false,
      });
    },

    update: (patch) => replaceCurrent({ ...patch, metaDirty: true }),
  };
});

/** The component being edited, if any. */
export function useCurrentSession(): ComponentSession | undefined {
  return useComponentStore((state) => current(state.sessions));
}

export function useRuntimePrefix(): string | null {
  return useComponentStore((state) => runtimePrefix(state.sessions));
}
