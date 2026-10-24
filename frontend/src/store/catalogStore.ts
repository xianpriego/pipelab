// Element catalog: summaries for the palette/canvas and lazily loaded details.

import { create } from "zustand";
import { ApiError, api, errorMessage } from "../api/client";
import type { ElementInfo, ElementSummary, Health } from "../api/types";

export type CatalogLoadState = "idle" | "loading" | "building" | "ready" | "error";

interface CatalogStore {
  elements: ElementSummary[];
  byName: Record<string, ElementSummary>;
  details: Record<string, ElementInfo>;
  state: CatalogLoadState;
  health: Health | null;
  error: string | null;
  load: () => Promise<void>;
  /** Re-reads the summaries (the component library changed) and forgets component details. */
  refresh: () => Promise<void>;
  loadDetails: (factory: string) => Promise<ElementInfo | null>;
}

const POLL_MS = 1500;
const pendingDetails = new Map<string, Promise<ElementInfo | null>>();

export const useCatalogStore = create<CatalogStore>((set, get) => ({
  elements: [],
  byName: {},
  details: {},
  state: "idle",
  health: null,
  error: null,

  load: async () => {
    if (get().state === "loading" || get().state === "ready") return;
    set({ state: "loading", error: null });
    for (;;) {
      try {
        const health = await api.health();
        set({ health });
        if (health.catalog.state === "error") {
          set({ state: "error", error: health.catalog.error ?? "Catalog build failed" });
          return;
        }
        if (health.catalog.state !== "ready") {
          set({ state: "building" });
          await new Promise((resolve) => setTimeout(resolve, POLL_MS));
          continue;
        }
        const elements = await api.catalog();
        const byName = Object.fromEntries(elements.map((element) => [element.name, element]));
        set({ elements, byName, state: "ready" });
        return;
      } catch (error) {
        if (error instanceof ApiError && error.status === 503) {
          set({ state: "building" });
          await new Promise((resolve) => setTimeout(resolve, POLL_MS));
          continue;
        }
        set({ state: "error", error: errorMessage(error) });
        return;
      }
    }
  },

  refresh: async () => {
    try {
      const elements = await api.catalog();
      const byName = Object.fromEntries(elements.map((element) => [element.name, element]));
      const details = Object.fromEntries(
        Object.entries(get().details).filter(([name]) => !name.startsWith("component:")),
      );
      set({ elements, byName, details, state: "ready" });
    } catch {
      // Keep the current catalog; the next refresh will try again.
    }
  },

  loadDetails: (factory) => {
    const cached = get().details[factory];
    if (cached) return Promise.resolve(cached);
    let pending = pendingDetails.get(factory);
    if (!pending) {
      pending = api
        .element(factory)
        .then((info) => {
          set((state) => ({ details: { ...state.details, [factory]: info } }));
          return info;
        })
        .catch(() => null)
        .finally(() => pendingDetails.delete(factory));
      pendingDetails.set(factory, pending);
    }
    return pending;
  },
}));
