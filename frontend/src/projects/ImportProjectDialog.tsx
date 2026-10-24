import { useState } from "react";
import { api, errorMessage } from "../api/client";
import type { Graph } from "../api/types";
import { Dialog } from "../components/Dialog";
import { cleanLaunchLine, parsePipelabJson } from "../lib/importDoc";
import { notify } from "../store/uiStore";

interface ImportProjectDialogProps {
  onClose: () => void;
  onCreated: (id: string) => void;
}

type Mode = "launch" | "json";

const EXAMPLE = "gst-launch-1.0 videotestsrc is-live=true ! videoconvert ! x264enc tune=zerolatency ! h264parse ! mp4mux ! filesink location=out.mp4";

export function ImportProjectDialog({ onClose, onCreated }: ImportProjectDialogProps) {
  const [mode, setMode] = useState<Mode>("launch");
  const [name, setName] = useState("Imported pipeline");
  const [line, setLine] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const create = async (graph: Graph, projectName: string, warnings: string[] = []) => {
    const project = await api.createProject({ name: projectName, graph });
    if (warnings.length) notify({ level: "warning", title: "Imported with warnings", details: warnings });
    onCreated(project.id);
  };

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      if (mode === "launch") {
        const result = await api.importGstLaunch(cleanLaunchLine(line));
        await create(result.graph, name, result.warnings);
      } else if (file) {
        const doc = parsePipelabJson(await file.text());
        await create(doc.graph, doc.name ?? name);
      }
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  const ready = mode === "launch" ? line.trim().length > 0 : file !== null;
  return (
    <Dialog
      title="Import pipeline"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={!ready || busy} onClick={() => void submit()}>
            {busy ? <span className="spinner" /> : null} Import
          </button>
        </>
      }
    >
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={mode === "launch"} className={`tab${mode === "launch" ? " active" : ""}`}
          onClick={() => setMode("launch")}>gst-launch line</button>
        <button role="tab" aria-selected={mode === "json"} className={`tab${mode === "json" ? " active" : ""}`}
          onClick={() => setMode("json")}>Pipelab JSON</button>
      </div>
      <label className="field">
        Name
        <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      {mode === "launch" ? (
        <label className="field">
          Pipeline description
          <textarea className="textarea" rows={6} placeholder={EXAMPLE} value={line} autoFocus
            onChange={(e) => setLine(e.target.value)} />
        </label>
      ) : (
        <label className="field">
          File exported from Pipelab
          <input className="input" type="file" accept=".json,application/json"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
        </label>
      )}
      {error ? <div className="badge error">{error}</div> : null}
    </Dialog>
  );
}
