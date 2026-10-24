import { useMemo } from "react";
import { graphSignature } from "../lib/graphSignature";
import { useGraphStore } from "../store/graphStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { startPipeline } from "./actions";

const RUNNING = new Set(["ready", "paused", "playing", "error"]);

/** Shown when the edited graph no longer matches the running pipeline. */
export function RestartHint() {
  const graph = useGraphStore((state) => state.graph);
  const runningGraph = useRuntimeStore((state) => state.runningGraph);
  const state = useRuntimeStore((state) => state.state);
  const stale = useMemo(
    () => runningGraph !== null && graphSignature(graph) !== graphSignature(runningGraph),
    [graph, runningGraph],
  );
  if (!stale || !RUNNING.has(state)) return null;
  return (
    <button className="btn btn-sm restart-hint" onClick={() => void startPipeline()}
      title="The graph changed since the pipeline started; structural changes need a restart">
      Edited · Restart
    </button>
  );
}
