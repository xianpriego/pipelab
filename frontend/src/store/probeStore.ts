// Probed links and the buffers/events received from them.

import { create } from "zustand";
import type { ProbeEvent } from "../api/events";
import { emptyProbeData, ingestProbe, type ProbeData } from "../lib/probes";

interface ProbeStore extends ProbeData {
  /** Links currently probed in the running pipeline. */
  probed: string[];
  paused: boolean;
  ingest: (event: ProbeEvent) => void;
  setProbed: (edgeId: string, probed: boolean) => void;
  setPaused: (paused: boolean) => void;
  clear: () => void;
  /** The run ended: probes are gone, collected rows stay for inspection. */
  endRun: () => void;
  reset: () => void;
}

export const useProbeStore = create<ProbeStore>((set) => ({
  ...emptyProbeData(),
  probed: [],
  paused: false,
  ingest: (event) => set((state) => ingestProbe(state, event, state.paused)),
  setProbed: (edgeId, probed) =>
    set((state) => ({
      probed: probed ? [...new Set([...state.probed, edgeId])] : state.probed.filter((id) => id !== edgeId),
    })),
  setPaused: (paused) => set({ paused }),
  clear: () => set({ ...emptyProbeData() }),
  endRun: () => set({ probed: [] }),
  reset: () => set({ ...emptyProbeData(), probed: [], paused: false }),
}));
