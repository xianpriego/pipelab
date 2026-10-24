// Probed links and the buffers/events received from them.

import { create } from "zustand";
import type { ProbeEvent, ProbeLogEvent, ScriptEvent } from "../api/events";
import { emptyProbeData, ingestProbe, ingestProbeLog, ingestScript, type ProbeData } from "../lib/probes";

interface ProbeStore extends ProbeData {
  /** Links currently probed in the running pipeline. */
  probed: string[];
  paused: boolean;
  ingest: (event: ProbeEvent) => void;
  ingestScript: (event: ScriptEvent) => void;
  ingestProbeLog: (event: ProbeLogEvent, probeName: string) => void;
  setProbed: (edgeId: string, probed: boolean) => void;
  setPaused: (paused: boolean) => void;
  clear: () => void;
  /** Script messages are replayed by the server on (re)connection: drop ours first. */
  clearScripts: () => void;
  /** The run ended: probes are gone, collected rows stay for inspection. */
  endRun: () => void;
  reset: () => void;
}

export const useProbeStore = create<ProbeStore>((set) => ({
  ...emptyProbeData(),
  probed: [],
  paused: false,
  ingest: (event) => set((state) => ingestProbe(state, event, state.paused)),
  ingestScript: (event) => set((state) => ingestScript(state, event, state.paused)),
  ingestProbeLog: (event, probeName) => set((state) => ingestProbeLog(state, event, probeName, state.paused)),
  setProbed: (edgeId, probed) =>
    set((state) => ({
      probed: probed ? [...new Set([...state.probed, edgeId])] : state.probed.filter((id) => id !== edgeId),
    })),
  setPaused: (paused) => set({ paused }),
  clear: () => set({ ...emptyProbeData() }),
  clearScripts: () => set((state) => ({ rows: state.rows.filter((row) => !row.scriptId && !row.probeId) })),
  endRun: () => set({ probed: [] }),
  reset: () => set({ ...emptyProbeData(), probed: [], paused: false }),
}));
