import { useState, type FormEvent } from "react";
import { Dialog } from "../../components/Dialog";
import { slugify } from "../../lib/components";
import { useComponentStore } from "../../store/componentStore";

const ID_PATTERN = /^[a-z0-9][a-z0-9-]*$/;

interface ComponentNameDialogProps {
  title: string;
  confirmLabel: string;
  hint?: string;
  initialName?: string;
  onSubmit: (name: string, id: string) => Promise<boolean>;
  onClose: () => void;
}

/** Name + library id of a new component (the id follows the name until edited). */
export function ComponentNameDialog({ title, confirmLabel, hint, initialName = "", onSubmit, onClose }: ComponentNameDialogProps) {
  const library = useComponentStore((state) => state.library);
  const [name, setName] = useState(initialName);
  const [id, setId] = useState(slugify(initialName));
  const [idEdited, setIdEdited] = useState(false);
  const [busy, setBusy] = useState(false);
  const taken = library.some((component) => component.id === id);
  const error = !name.trim() ? "Give it a name"
    : !ID_PATTERN.test(id) ? "The id uses lowercase letters, digits and dashes"
      : taken ? `A component "${id}" already exists` : null;

  const submit = async (event?: FormEvent) => {
    event?.preventDefault();
    if (error || busy) return;
    setBusy(true);
    const done = await onSubmit(name.trim(), id);
    setBusy(false);
    if (done) onClose();
  };

  return (
    <Dialog title={title} onClose={onClose} footer={
      <>
        <span className="muted">{error ?? `Saved in the library as component:${id}`}</span>
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={Boolean(error) || busy} onClick={() => void submit()}>
          {busy ? <span className="spinner" /> : null} {confirmLabel}
        </button>
      </>
    }>
      <form className="form-grid" onSubmit={(event) => void submit(event)}>
        {hint ? <p className="muted">{hint}</p> : null}
        <label className="field">
          Name
          <input className="input" autoFocus value={name} placeholder="RTSP input" onChange={(event) => {
            setName(event.target.value);
            if (!idEdited) setId(slugify(event.target.value));
          }} />
        </label>
        <label className="field">
          Library id
          <input className="input mono" value={id} placeholder="rtsp-input" onChange={(event) => {
            setId(event.target.value);
            setIdEdited(true);
          }} />
        </label>
        <button type="submit" hidden />
      </form>
    </Dialog>
  );
}
