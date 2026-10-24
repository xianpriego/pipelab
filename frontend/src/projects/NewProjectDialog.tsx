import { useEffect, useState } from "react";
import { api, errorMessage } from "../api/client";
import type { TemplateInfo } from "../api/types";
import { Dialog } from "../components/Dialog";

interface NewProjectDialogProps {
  onClose: () => void;
  onCreated: (id: string) => void;
}

export function NewProjectDialog({ onClose, onCreated }: NewProjectDialogProps) {
  const [name, setName] = useState("Untitled pipeline");
  const [description, setDescription] = useState("");
  const [template, setTemplate] = useState<string | null>(null);
  const [templates, setTemplates] = useState<TemplateInfo[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.templates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  const create = async () => {
    setBusy(true);
    setError(null);
    try {
      const project = await api.createProject({ name: name.trim() || "Untitled pipeline", description, template });
      onCreated(project.id);
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  };

  return (
    <Dialog
      title="New pipeline"
      onClose={onClose}
      footer={
        <>
          <button className="btn" onClick={onClose}>Cancel</button>
          <button className="btn btn-primary" disabled={busy} onClick={() => void create()}>
            {busy ? <span className="spinner" /> : null} Create
          </button>
        </>
      }
    >
      <label className="field">
        Name
        <input className="input" autoFocus value={name} onChange={(e) => setName(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void create()} />
      </label>
      <label className="field">
        Description
        <input className="input" value={description} placeholder="Optional" onChange={(e) => setDescription(e.target.value)} />
      </label>
      <div className="field">
        <span className="muted">Start from</span>
        <div className="template-list">
          <TemplateOption id={null} title="Empty canvas" description="Start from scratch." selected={template === null}
            onSelect={setTemplate} />
          {templates.map((t) => (
            <TemplateOption key={t.id} id={t.id} title={t.name} description={t.description} selected={template === t.id}
              disabled={!t.available} missing={t.missing} onSelect={setTemplate} />
          ))}
        </div>
      </div>
      {error ? <div className="badge error">{error}</div> : null}
    </Dialog>
  );
}

interface TemplateOptionProps {
  id: string | null;
  title: string;
  description: string;
  selected: boolean;
  disabled?: boolean;
  missing?: string[];
  onSelect: (id: string | null) => void;
}

function TemplateOption({ id, title, description, selected, disabled, missing, onSelect }: TemplateOptionProps) {
  return (
    <button type="button" className={`template-option${selected ? " selected" : ""}`} disabled={disabled}
      onClick={() => onSelect(id)}>
      <strong>{title}</strong>
      <span className="muted">{description}</span>
      {disabled && missing?.length ? <span className="badge warning">Missing: {missing.join(", ")}</span> : null}
    </button>
  );
}
