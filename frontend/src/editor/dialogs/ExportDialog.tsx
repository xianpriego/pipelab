import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { ExportFormat, ExportResult } from "../../api/types";
import { CodeView } from "../../components/CodeView";
import { Dialog } from "../../components/Dialog";
import { Icon } from "../../components/Icon";
import { downloadText } from "../../lib/download";
import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { notify, useUiStore } from "../../store/uiStore";

function download(result: ExportResult) {
  downloadText(result.content, result.filename);
}

export function ExportDialog() {
  const close = useUiStore((state) => state.openDialog);
  const graph = useGraphStore((state) => state.graph);
  const name = useProjectStore((state) => state.meta?.name ?? "pipeline");
  const [formats, setFormats] = useState<ExportFormat[]>([]);
  const [format, setFormat] = useState<string>("gst-launch");
  const [result, setResult] = useState<ExportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.exportFormats().then(setFormats).catch((err) => setError(errorMessage(err)));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setResult(null);
    setError(null);
    api
      .exportGraph(graph, format, name)
      .then((value) => !cancelled && setResult(value))
      .catch((err) => !cancelled && setError(errorMessage(err)));
    return () => {
      cancelled = true;
    };
  }, [graph, format, name]);

  const copy = async () => {
    if (!result) return;
    try {
      await navigator.clipboard.writeText(result.content);
      notify({ level: "success", title: "Copied to the clipboard" });
    } catch {
      notify({ level: "warning", title: "Clipboard unavailable", message: "Select the text and copy it manually." });
    }
  };

  const current = formats.find((f) => f.id === format);
  return (
    <Dialog title="Export pipeline" wide onClose={() => close(null)} footer={
      <>
        <button className="btn" disabled={!result} onClick={() => void copy()}><Icon name="copy" /> Copy</button>
        <button className="btn btn-primary" disabled={!result} onClick={() => result && download(result)}>
          <Icon name="download" /> Download {result?.filename}
        </button>
      </>
    }>
      <div className="tabs" role="tablist">
        {(formats.length ? formats : [{ id: "gst-launch", label: "gst-launch" } as ExportFormat]).map((f) => (
          <button key={f.id} role="tab" aria-selected={f.id === format}
            className={`tab${f.id === format ? " active" : ""}`} onClick={() => setFormat(f.id)}>
            {f.label}
          </button>
        ))}
      </div>
      {current ? <div className="muted">{current.description}</div> : null}
      {error ? <div className="badge error">{error}</div> : null}
      {result ? <CodeView code={result.content} language={result.language} /> : !error ? <span className="spinner" /> : null}
    </Dialog>
  );
}
