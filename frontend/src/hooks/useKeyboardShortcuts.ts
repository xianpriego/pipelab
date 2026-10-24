import { useEffect } from "react";
import { saveProject } from "../editor/actions";
import { useComponentStore } from "../store/componentStore";
import { useGraphStore } from "../store/graphStore";
import { useUiStore } from "../store/uiStore";

function isTyping(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  if (!element) return false;
  return element.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(element.tagName);
}

/** Ctrl+S save (the open component, if any), Ctrl+Z / Ctrl+Shift+Z undo/redo, Ctrl+C / Ctrl+V copy/paste nodes. */
export function useKeyboardShortcuts(): void {
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const mod = event.ctrlKey || event.metaKey;
      if (!mod) return;
      const key = event.key.toLowerCase();
      if (key === "s") {
        event.preventDefault();
        if (useComponentStore.getState().sessions.length) void useComponentStore.getState().save();
        else void saveProject();
        return;
      }
      if (isTyping(event.target)) return;
      const graph = useGraphStore.getState();
      if (key === "z" && !event.shiftKey) {
        event.preventDefault();
        graph.undo();
      } else if ((key === "z" && event.shiftKey) || key === "y") {
        event.preventDefault();
        graph.redo();
      } else if (key === "c") {
        graph.copy(useUiStore.getState().selectedNodes);
      } else if (key === "v") {
        const ids = graph.paste();
        if (ids.length) useUiStore.getState().select(ids, []);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
}
