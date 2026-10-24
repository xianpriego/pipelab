// Metadata of the open project and its save state (the graph lives in graphStore).

import { create } from "zustand";
import type { Project, ProjectSettings } from "../api/types";

export type SaveState = "saved" | "dirty" | "saving" | "error";

export interface ProjectMeta {
  id: string;
  name: string;
  description: string;
  settings: ProjectSettings;
  updated_at: string;
}

interface ProjectStore {
  meta: ProjectMeta | null;
  metaRevision: number;
  saveState: SaveState;
  saveError: string | null;
  open: (project: Project) => void;
  close: () => void;
  rename: (name: string) => void;
  setDescription: (description: string) => void;
  setSettings: (settings: ProjectSettings) => void;
  setSaveState: (state: SaveState, error?: string | null) => void;
}

export const useProjectStore = create<ProjectStore>((set) => ({
  meta: null,
  metaRevision: 0,
  saveState: "saved",
  saveError: null,
  open: (project) =>
    set({
      meta: {
        id: project.id,
        name: project.name,
        description: project.description,
        settings: project.settings,
        updated_at: project.updated_at,
      },
      saveState: "saved",
      saveError: null,
    }),
  close: () => set({ meta: null, saveState: "saved", saveError: null }),
  rename: (name) =>
    set((state) => (state.meta ? { meta: { ...state.meta, name }, metaRevision: state.metaRevision + 1 } : state)),
  setDescription: (description) =>
    set((state) =>
      state.meta ? { meta: { ...state.meta, description }, metaRevision: state.metaRevision + 1 } : state,
    ),
  setSettings: (settings) =>
    set((state) => (state.meta ? { meta: { ...state.meta, settings }, metaRevision: state.metaRevision + 1 } : state)),
  setSaveState: (saveState, error = null) => set({ saveState, saveError: error }),
}));
