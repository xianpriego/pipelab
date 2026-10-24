import { useState } from "react";
import type { Slot, Value } from "../../api/dynamic";
import { Dialog } from "../../components/Dialog";
import { addLiveInstance } from "./slotActions";
import { ParamsForm } from "./ParamsForm";

/** Parameters of a new live instance → add_<item>(params) on the running pipeline. */
export function AddInstanceDialog({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const [params, setParams] = useState<Record<string, Value>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const add = async () => {
    setBusy(true);
    const result = await addLiveInstance(slot, params);
    setBusy(false);
    if (result.ok) onClose();
    else setError(result.error ?? "The call failed");
  };

  return (
    <Dialog title={`Add ${slot.item}`} onClose={onClose} footer={
      <>
        <span className="mono muted">add_{slot.item}({Object.keys(params).join(", ")})</span>
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={busy} onClick={() => void add()}>
          {busy ? <span className="spinner" /> : null} Add instance
        </button>
      </>
    }>
      {error ? <div className="badge error call-error">{error}</div> : null}
      <ParamsForm component={slot.component} params={params} onChange={setParams} label={`Parameters of the new ${slot.item}`} />
    </Dialog>
  );
}
