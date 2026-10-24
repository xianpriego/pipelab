import { lazy, Suspense, useMemo, useState } from "react";
import type { ProbeScript } from "../../api/types";
import { Dialog } from "../../components/Dialog";
import { issueLines, scriptIssues, targetLabel } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useValidationStore } from "../../store/validationStore";
import { ScriptHelp } from "./ScriptHelp";

const CodeEditor = lazy(() => import("./CodeEditor"));

interface ScriptEditorDialogProps {
  script: ProbeScript;
  onClose: () => void;
}

/** Edits a probe script; changes are committed to the graph (undoable) on Save. */
export function ScriptEditorDialog({ script, onClose }: ScriptEditorDialogProps) {
  const graph = useGraphStore((state) => state.graph);
  const allIssues = useValidationStore((state) => state.issues);
  const issues = useMemo(() => scriptIssues(allIssues, script), [allIssues, script]);
  const [name, setName] = useState(script.name);
  const [enabled, setEnabled] = useState(script.enabled);
  const [code, setCode] = useState(script.code);
  const dirty = name !== script.name || enabled !== script.enabled || code !== script.code;

  const save = () => {
    if (dirty) useGraphStore.getState().updateScript(script.id, { name: name.trim() || "Script", enabled, code });
  };
  const close = () => {
    if (dirty && !window.confirm("Discard the unsaved changes of this script?")) return;
    onClose();
  };
  const footer = (
    <>
      <span className="muted">{dirty ? "Unsaved changes · Ctrl+S saves" : "Saved"}</span>
      <span className="spacer" />
      <button className="btn" onClick={close}>Close</button>
      <button className="btn btn-primary" disabled={!dirty} onClick={() => { save(); onClose(); }}>Save</button>
    </>
  );
  return (
    <Dialog title={`Script on ${targetLabel(graph, script.target)}`} onClose={close} footer={footer} wide>
      <div className="row script-meta">
        <label className="field grow">
          Name
          <input className="input" value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className="row nowrap" title="Disabled scripts are kept but not run">
          <span className="switch">
            <input type="checkbox" checked={enabled} aria-label="Script enabled"
              onChange={(event) => setEnabled(event.target.checked)} />
            <span />
          </span>
          Enabled
        </label>
      </div>
      {issues.length ? (
        <ul className="script-issues" aria-label="Script problems">
          {issues.map((issue) => (
            <li key={issue.id} className={`badge ${issue.severity}`}>{issue.message}</li>
          ))}
        </ul>
      ) : null}
      <div className="script-editor-layout">
        <Suspense fallback={<div className="code-editor loading"><span className="spinner" /></div>}>
          <CodeEditor value={code} onChange={setCode} onSave={save} errorLines={issueLines(issues)}
            ariaLabel={`Code of ${script.name}`} />
        </Suspense>
        <ScriptHelp />
      </div>
    </Dialog>
  );
}
