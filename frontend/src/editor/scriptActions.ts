// Commands on probe scripts: add from recipes, trigger them while running.

import { api, errorMessage } from "../api/client";
import type { ProbeScript, PropertyValue, ScriptRecipe, ScriptTarget } from "../api/types";
import { createScript } from "../lib/scripts";
import { useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";
import { useRecipeStore } from "../store/recipeStore";
import { notify } from "../store/uiStore";

export const KEYFRAME_SWITCH = "keyframe-switch";

export function addScriptFromRecipe(recipe: ScriptRecipe, target: ScriptTarget): ProbeScript {
  const script = createScript(target, recipe.name, recipe.code);
  useGraphStore.getState().addScript(script);
  return script;
}

/** Adds the "switch on keyframe" recipe to a selector element. */
export async function addKeyframeSwitch(nodeId: string): Promise<ProbeScript | null> {
  const recipes = await useRecipeStore.getState().load();
  const recipe = recipes.find((r) => r.id === KEYFRAME_SWITCH);
  if (!recipe) {
    notify({ level: "error", title: "Recipe not available", message: useRecipeStore.getState().error ?? undefined });
    return null;
  }
  return addScriptFromRecipe(recipe, { kind: "node", id: nodeId });
}

/** Calls ``on_trigger(ctx, value)`` of a running script. */
export async function triggerScript(script: ProbeScript, value: PropertyValue | null): Promise<boolean> {
  const meta = useProjectStore.getState().meta;
  if (!meta) return false;
  try {
    const result = await api.runtimeTrigger(meta.id, script.id, value);
    if (!result.ok) {
      notify({ level: "error", title: `Trigger of "${script.name}" failed`, message: result.error ?? undefined });
      return false;
    }
    notify({ level: "success", title: `Triggered "${script.name}"`, timeout: 2500 });
    return true;
  } catch (error) {
    notify({ level: "error", title: `Trigger of "${script.name}" failed`, message: errorMessage(error) });
    return false;
  }
}

/** Text typed in a trigger box as a JSON-ish primitive ("" → null, "3" → 3, "true" → true). */
export function parseTriggerValue(text: string): PropertyValue | null {
  const value = text.trim();
  if (!value) return null;
  if (value === "true" || value === "false") return value === "true";
  const number = Number(value);
  return Number.isFinite(number) && /^-?\d/.test(value) ? number : value;
}
