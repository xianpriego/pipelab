import { saveProject } from "./actions";
import { useProjectStore } from "../store/projectStore";

const LABELS = { saved: "Saved", dirty: "Unsaved changes", saving: "Saving…", error: "Save failed" } as const;

export function SaveIndicator() {
  const state = useProjectStore((s) => s.saveState);
  const error = useProjectStore((s) => s.saveError);
  return (
    <button className={`save-indicator ${state}`} title={error ?? "Ctrl+S to save now"} onClick={() => void saveProject()}>
      <span className="dot" />
      {LABELS[state]}
    </button>
  );
}
