import { useEffect } from "react";
import type { ProbeScript, ScriptTarget } from "../../api/types";
import { BLANK_SCRIPT, createScript, recipesFor } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useRecipeStore } from "../../store/recipeStore";
import { addScriptFromRecipe } from "../scriptActions";

interface RecipePickerProps {
  target: ScriptTarget;
  factory?: string;
  onAdded: (script: ProbeScript) => void;
  onCancel: () => void;
}

/** Ready-made scripts for this element or link, plus a blank one. */
export function RecipePicker({ target, factory, onAdded, onCancel }: RecipePickerProps) {
  const { recipes, state, error, load } = useRecipeStore();
  useEffect(() => {
    void load();
  }, [load]);
  const available = recipesFor(recipes, target.kind, factory);

  const addBlank = () => {
    const script = createScript(target, "Custom script", BLANK_SCRIPT);
    useGraphStore.getState().addScript(script);
    onAdded(script);
  };
  return (
    <div className="recipe-picker" role="list" aria-label="Script recipes">
      {state === "loading" ? <span className="spinner" /> : null}
      {state === "error" ? <div className="badge error">{error}</div> : null}
      {available.map((recipe) => (
        <div key={recipe.id} role="listitem">
          <button className="recipe-option" onClick={() => onAdded(addScriptFromRecipe(recipe, target))}>
            <strong>{recipe.name}</strong>
            <span className="muted">{recipe.description}</span>
          </button>
        </div>
      ))}
      <div role="listitem">
        <button className="recipe-option" onClick={addBlank}>
          <strong>Blank script</strong>
          <span className="muted">Every callback stubbed, to write your own logic.</span>
        </button>
      </div>
      <button className="btn btn-sm btn-ghost" onClick={onCancel}>Cancel</button>
    </div>
  );
}
