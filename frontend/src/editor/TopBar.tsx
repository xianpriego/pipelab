import { Link } from "react-router-dom";
import { api, errorMessage } from "../api/client";
import { Icon } from "../components/Icon";
import { ThemeToggle } from "../components/ThemeToggle";
import { useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";
import { hasWorker } from "../store/runtimeReducer";
import { useRuntimeStore } from "../store/runtimeStore";
import { notify, useUiStore } from "../store/uiStore";
import { DebugLevelSelect } from "./DebugLevelSelect";
import { FlowToggle } from "./FlowToggle";
import { RunControls } from "./RunControls";
import { SaveIndicator } from "./SaveIndicator";
import { ValidationBadge } from "./ValidationBadge";

async function autoLayout() {
  try {
    const graph = await api.layout(useGraphStore.getState().graph);
    useGraphStore.getState().commit(graph);
    useUiStore.getState().requestFit();
  } catch (error) {
    notify({ level: "error", title: "Auto-layout failed", message: errorMessage(error) });
  }
}

export function TopBar() {
  const meta = useProjectStore((state) => state.meta);
  const rename = useProjectStore((state) => state.rename);
  const openDialog = useUiStore((state) => state.openDialog);
  const inspectable = useRuntimeStore((state) => hasWorker(state.state));
  const hasNodes = useGraphStore((state) => state.graph.nodes.length > 0);

  return (
    <header className="topbar">
      <Link to="/" className="icon-btn" title="All pipelines" aria-label="All pipelines">
        <Icon name="back" />
      </Link>
      <input
        className="project-name"
        value={meta?.name ?? ""}
        onChange={(event) => rename(event.target.value)}
        aria-label="Pipeline name"
      />
      <SaveIndicator />
      <ValidationBadge />
      <div className="topbar-sep" />
      <RunControls />
      <DebugLevelSelect />
      <span className="spacer" />
      <FlowToggle />
      <button className="btn btn-ghost" onClick={() => void autoLayout()} disabled={!hasNodes} title="Arrange elements left to right">
        <Icon name="layout" /> Layout
      </button>
      <button className="btn btn-ghost" onClick={() => openDialog("import")} title="Import a gst-launch line">
        <Icon name="import" /> Import
      </button>
      <button className="btn btn-ghost" onClick={() => openDialog("export")} disabled={!hasNodes} title="Export code">
        <Icon name="export" /> Export
      </button>
      <button className="btn btn-ghost" onClick={() => openDialog("runtime-graph")} disabled={!inspectable}
        title="Graph of the real running pipeline (negotiated caps)">
        <Icon name="graph" /> Runtime graph
      </button>
      <ThemeToggle />
    </header>
  );
}
