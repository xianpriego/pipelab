import { useState } from "react";
import { api } from "../../api/client";
import { Dialog } from "../../components/Dialog";
import { Icon } from "../../components/Icon";
import { useProjectStore } from "../../store/projectStore";
import { useUiStore } from "../../store/uiStore";

export function RuntimeGraphDialog() {
  const close = useUiStore((state) => state.openDialog);
  const projectId = useProjectStore((state) => state.meta?.id);
  const [url, setUrl] = useState(() => (projectId ? api.runtimeDotUrl(projectId) : ""));
  const [zoom, setZoom] = useState(1);
  const [failed, setFailed] = useState(false);

  return (
    <Dialog title="Runtime pipeline graph" wide onClose={() => close(null)} footer={
      <>
        <button className="btn" onClick={() => setZoom(Math.max(0.25, zoom - 0.25))}>−</button>
        <span className="muted">{Math.round(zoom * 100)}%</span>
        <button className="btn" onClick={() => setZoom(Math.min(4, zoom + 0.25))}>+</button>
        <button className="btn" onClick={() => {
          setFailed(false);
          if (projectId) setUrl(api.runtimeDotUrl(projectId));
        }}>
          <Icon name="refresh" /> Refresh
        </button>
        <a className="btn btn-primary" href={url} target="_blank" rel="noreferrer">Open SVG</a>
      </>
    }>
      <p className="muted">The real GStreamer pipeline (as dumped by GST_DEBUG_BIN_TO_DOT), including auto-plugged
        elements, preview branches and negotiated caps.</p>
      <div className="dot-view">
        {failed ? (
          <div className="empty-state">The graph is only available while the pipeline is running.</div>
        ) : (
          <img src={url} alt="Runtime pipeline graph" style={{ width: `${zoom * 100}%` }} onError={() => setFailed(true)} />
        )}
      </div>
    </Dialog>
  );
}
