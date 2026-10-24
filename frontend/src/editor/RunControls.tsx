import { Icon } from "../components/Icon";
import { formatClock } from "../lib/format";
import { useRuntimeStore } from "../store/runtimeStore";
import { pausePipeline, runPipeline, stopPipeline } from "./actions";
import { RestartHint } from "./RestartHint";

export function RunControls() {
  const state = useRuntimeStore((s) => s.state);
  const position = useRuntimeStore((s) => s.stats?.position ?? null);
  const connected = useRuntimeStore((s) => s.connected);
  const busy = state === "starting" || state === "stopping";
  // After an error the worker stays alive for inspection, so it can still be stopped.
  const live = state === "playing" || state === "paused" || state === "ready" || state === "error";

  return (
    <div className="run-controls">
      <button className="icon-btn run-play" title="Play" aria-label="Play" disabled={busy || state === "playing"}
        onClick={() => void runPipeline()}>
        <Icon name="play" />
      </button>
      <button className="icon-btn" title="Pause" aria-label="Pause" disabled={state !== "playing"}
        onClick={() => void pausePipeline()}>
        <Icon name="pause" />
      </button>
      <button className="icon-btn run-stop" title="Stop (send EOS so files are finalised)" aria-label="Stop" disabled={!live}
        onClick={() => void stopPipeline("eos")}>
        <Icon name="stop" />
      </button>
      <button className="icon-btn run-kill" title="Kill immediately" aria-label="Kill"
        disabled={!(live || busy)} onClick={() => void stopPipeline("kill")}>
        <Icon name="kill" />
      </button>
      <span className={`state-pill ${state}`} title={connected ? "Runtime connected" : "Runtime disconnected"}>
        {busy ? <span className="spinner" /> : <span className="dot" />}
        {state}
      </span>
      {live && state !== "error" ? <span className="mono muted">{formatClock(position)}</span> : null}
      <RestartHint />
    </div>
  );
}
