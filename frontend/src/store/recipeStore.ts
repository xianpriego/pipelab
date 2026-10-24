// Probe script recipes offered by the backend (loaded once, on demand).

import { create } from "zustand";
import { api, errorMessage } from "../api/client";
import type { ScriptRecipe } from "../api/types";

interface RecipeStore {
  recipes: ScriptRecipe[];
  state: "idle" | "loading" | "ready" | "error";
  error: string | null;
  load: () => Promise<ScriptRecipe[]>;
}

export const useRecipeStore = create<RecipeStore>((set, get) => ({
  recipes: [],
  state: "idle",
  error: null,
  load: async () => {
    if (get().state === "ready") return get().recipes;
    set({ state: "loading", error: null });
    try {
      const recipes = await api.scriptRecipes();
      set({ recipes, state: "ready" });
      return recipes;
    } catch (error) {
      set({ state: "error", error: errorMessage(error) });
      return [];
    }
  },
}));
