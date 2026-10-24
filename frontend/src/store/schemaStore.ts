// Probe rule schema (GET /api/probes/schema), with a built-in copy as fallback.

import { create } from "zustand";
import { api } from "../api/client";
import type { ProbeSchema } from "../api/dynamic";
import { FALLBACK_SCHEMA } from "../lib/probeSchema";

interface SchemaStore {
  schema: ProbeSchema;
  loaded: boolean;
  load: () => Promise<ProbeSchema>;
}

let pending: Promise<ProbeSchema> | null = null;

export const useSchemaStore = create<SchemaStore>((set, get) => ({
  schema: FALLBACK_SCHEMA,
  loaded: false,
  load: () => {
    if (get().loaded) return Promise.resolve(get().schema);
    pending ??= api
      .probeSchema()
      .then((schema) => {
        set({ schema, loaded: true });
        return schema;
      })
      .catch(() => {
        set({ loaded: true });
        return FALLBACK_SCHEMA;
      })
      .finally(() => {
        pending = null;
      });
    return pending;
  },
}));
