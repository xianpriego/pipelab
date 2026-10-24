// Runtime state of the open project (events reduced by runtimeReducer).

import { create } from "zustand";
import type { SlotInstance } from "../api/dynamic";
import type { RuntimeEvent } from "../api/events";
import type { Graph, PropertyValue, RuntimeStatus } from "../api/types";
import { applyRuntimeEvent, initialRuntime, liveKey, withoutPending, type RuntimeData } from "./runtimeReducer";

interface RuntimeStore extends RuntimeData {
  connected: boolean;
  /** Graph the running pipeline was built from (plus live property changes). */
  runningGraph: Graph | null;
  setRunningGraph: (graph: Graph | null) => void;
  /** Optimistic live value (confirmed or replaced by the worker's property event). */
  setLiveProp: (nodeId: string, property: string, value: PropertyValue | undefined, pad?: string | null) => void;
  /** Mark a requested value as deferred by a script until the element reports it. */
  setPending: (nodeId: string, property: string, value: PropertyValue | undefined, pad?: string | null) => void;
  apply: (event: RuntimeEvent) => void;
  setStatus: (status: RuntimeStatus) => void;
  setConnected: (connected: boolean) => void;
  setInstances: (slots: Record<string, SlotInstance[]>) => void;
  /** Drop run data before the websocket replays it after (re)connecting. */
  clearReplayed: () => void;
  reset: () => void;
}

export const useRuntimeStore = create<RuntimeStore>((set) => ({
  ...initialRuntime(),
  connected: false,
  runningGraph: null,
  setRunningGraph: (runningGraph) => set({ runningGraph }),
  setLiveProp: (nodeId, property, value, pad) =>
    set((state) => {
      const props = { ...state.liveProps[nodeId] };
      if (value === undefined) delete props[liveKey(property, pad)];
      else props[liveKey(property, pad)] = value;
      return { liveProps: { ...state.liveProps, [nodeId]: props } };
    }),
  setPending: (nodeId, property, value, pad) =>
    set((state) => {
      const key = liveKey(property, pad);
      if (value === undefined) return { pending: withoutPending(state.pending, nodeId, key) };
      return { pending: { ...state.pending, [nodeId]: { ...state.pending[nodeId], [key]: value } } };
    }),
  apply: (event) => set((state) => applyRuntimeEvent(state, event)),
  setStatus: (status) =>
    set((state) => {
      if (status.state === "starting" && state.state !== "starting") {
        return { ...initialRuntime(), state: "starting", seq: state.seq };
      }
      return { state: status.state, error: status.error ?? state.error };
    }),
  setConnected: (connected) => set({ connected }),
  clearReplayed: () =>
    set({
      bus: [], logs: [], caps: {}, stats: null, nodeAlerts: {}, edgeAlerts: {}, liveProps: {}, pending: {}, instances: {},
    }),
  setInstances: (slots) => set({ instances: slots }),
  reset: () => set({ ...initialRuntime(), connected: false, runningGraph: null }),
}));
