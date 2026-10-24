import { useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { Graph } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { cleanLaunchLine } from "../../lib/importDoc";
import { pasteSubgraph } from "../../lib/graphOps";
import { useGraphStore } from "../../store/graphStore";
import { notify, useUiStore } from "../../store/uiStore";

function belowExisting(graph: Graph): number {
  return graph.nodes.reduce((max, node) => Math.max(max, node.position.y), -Infinity) + 180;
}

export function ImportGraphDialog() {
  const close = useUiStore((state) => state.openDialog);
  const [line, setLine] = useState("");
  const [replace, setReplace] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.importGstLaunch(cleanLaunchLine(line));
      const store = useGraphStore.getState();
      if (replace || store.graph.nodes.length === 0) store.commit(result.graph);
      else store.commit(pasteSubgraph(store.graph, result.graph, { x: 0, y: belowExisting(store.graph) }).graph);
      useUiStore.getState().requestFit();
      if (result.warnings.length) notify({ level: "warning", title: "Imported with warnings", details: result.warnings });
      close(null);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Dialog title="Import gst-launch pipeline" onClose={() => close(null)} footer={
      <>
        <button className="btn" onClick={() => close(null)}>Cancel</button>
        <button className="btn btn-primary" disabled={!line.trim() || busy} onClick={() => void submit()}>
          {busy ? <span className="spinner" /> : null} Import
        </button>
      </>
    }>
      <label className="field">
        Pipeline description (with or without <code>gst-launch-1.0</code>)
        <textarea className="textarea" rows={7} autoFocus value={line} onChange={(e) => setLine(e.target.value)}
          placeholder="videotestsrc ! videoconvert ! autovideosink" />
      </label>
      <label className="row">
        <input type="checkbox" checked={replace} onChange={(e) => setReplace(e.target.checked)} />
        Replace the current canvas (otherwise the pipeline is added below it)
      </label>
      {error ? <div className="badge error">{error}</div> : null}
    </Dialog>
  );
}
