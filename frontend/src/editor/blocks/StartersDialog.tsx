import { useEffect, useState } from "react";
import { api, errorMessage } from "../../api/client";
import type { StarterInfo } from "../../api/dynamic";
import { Dialog } from "../../components/Dialog";
import { useComponentStore } from "../../store/componentStore";
import { installStarter } from "./componentActions";

/** Ready-made components (RTSP inputs, encoders, recorders, outputs) to add to the library. */
export function StartersDialog({ onClose }: { onClose: () => void }) {
  const library = useComponentStore((state) => state.library);
  const [starters, setStarters] = useState<StarterInfo[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  useEffect(() => {
    api.listStarters().then(setStarters).catch((err) => setError(errorMessage(err)));
  }, []);

  const install = async (starter: StarterInfo) => {
    setBusy(starter.id);
    await installStarter(starter.id, starter.name);
    setBusy(null);
  };

  return (
    <Dialog title="Starter components" onClose={onClose} footer={
      <>
        <span className="muted">They become normal components: open them to adapt them to your setup.</span>
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Close</button>
      </>
    }>
      {error ? <div className="badge error">{error}</div> : null}
      {!starters && !error ? <span className="spinner" /> : null}
      <ul className="starter-list" aria-label="Starter components">
        {starters?.map((starter) => {
          const installed = library.some((component) => component.id === starter.id);
          return (
            <li key={starter.id} className="starter-row">
              <div className="starter-text">
                <strong>{starter.name}</strong> <span className="faint mono">component:{starter.id}</span>
                <p className="muted">{starter.description}</p>
                {starter.missing.length ? (
                  <p className="badge warning">Not installed here: {starter.missing.join(", ")}</p>
                ) : null}
              </div>
              <button className="btn btn-sm" disabled={installed || busy !== null}
                aria-label={`Add ${starter.name}`} onClick={() => void install(starter)}>
                {busy === starter.id ? <span className="spinner" /> : null}
                {installed ? "In the library" : "Add"}
              </button>
            </li>
          );
        })}
      </ul>
    </Dialog>
  );
}
