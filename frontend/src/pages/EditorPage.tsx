import { ReactFlowProvider } from "@xyflow/react";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { Canvas } from "../editor/canvas/Canvas";
import { ExportDialog } from "../editor/dialogs/ExportDialog";
import { ImportGraphDialog } from "../editor/dialogs/ImportGraphDialog";
import { RuntimeGraphDialog } from "../editor/dialogs/RuntimeGraphDialog";
import { Dock } from "../editor/dock/Dock";
import { Inspector } from "../editor/inspector/Inspector";
import { Palette } from "../editor/palette/Palette";
import { TopBar } from "../editor/TopBar";
import { useAutosave } from "../hooks/useAutosave";
import { useKeyboardShortcuts } from "../hooks/useKeyboardShortcuts";
import { useRuntimeConnection } from "../hooks/useRuntimeConnection";
import { useValidation } from "../hooks/useValidation";
import { useComponentStore } from "../store/componentStore";
import { useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";
import { useUiStore } from "../store/uiStore";
import { useValidationStore } from "../store/validationStore";

export function EditorPage() {
  const { id } = useParams<{ id: string }>();
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialog = useUiStore((state) => state.dialog);
  const dockOpen = useUiStore((state) => state.dockOpen);
  const dockHeight = useUiStore((state) => state.dockHeight);

  useEffect(() => {
    if (!id) return undefined;
    let cancelled = false;
    setLoaded(false);
    setError(null);
    api
      .getProject(id)
      .then((project) => {
        if (cancelled) return;
        // Component definitions left open by a previous project are dropped (not saved).
        useComponentStore.getState().exitTo(0);
        useGraphStore.getState().load(project.graph);
        void useComponentStore.getState().loadLibrary();
        useProjectStore.getState().open(project);
        useValidationStore.getState().setIssues([]);
        useUiStore.getState().select([], []);
        setLoaded(true);
      })
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
      useProjectStore.getState().close();
    };
  }, [id]);

  useAutosave(loaded);
  useValidation(loaded);
  useRuntimeConnection(loaded ? id : undefined);
  useKeyboardShortcuts();

  if (error) {
    return (
      <div className="empty-state editor-error">
        <h3>Could not open this pipeline</h3>
        <p>{error}</p>
        <Link to="/">Back to pipelines</Link>
      </div>
    );
  }
  if (!loaded) {
    return (
      <div className="empty-state editor-error">
        <span className="spinner" />
      </div>
    );
  }

  return (
    <ReactFlowProvider>
      <div className="editor" style={{ gridTemplateRows: `48px minmax(0, 1fr) ${dockOpen ? dockHeight : 34}px` }}>
        <TopBar />
        <div className="editor-main">
          <Palette />
          <Canvas />
          <Inspector />
        </div>
        <Dock />
      </div>
      {dialog === "export" ? <ExportDialog /> : null}
      {dialog === "import" ? <ImportGraphDialog /> : null}
      {dialog === "runtime-graph" ? <RuntimeGraphDialog /> : null}
    </ReactFlowProvider>
  );
}
