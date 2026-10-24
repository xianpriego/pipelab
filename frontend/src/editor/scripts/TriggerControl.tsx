import { useState } from "react";
import type { ProbeScript } from "../../api/types";
import { Icon } from "../../components/Icon";
import { parseTriggerValue, triggerScript } from "../scriptActions";

/** Button calling the script's on_trigger(ctx, value), with an optional value. */
export function TriggerControl({ script, disabled }: { script: ProbeScript; disabled: boolean }) {
  const [value, setValue] = useState("");
  return (
    <div className="row trigger-control">
      <input className="input input-sm" placeholder="value (optional)" value={value} disabled={disabled}
        aria-label={`Trigger value for ${script.name}`} onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => event.key === "Enter" && void triggerScript(script, parseTriggerValue(value))} />
      <button className="btn btn-sm" disabled={disabled} title={disabled ? "Available while running" : "Call on_trigger(ctx, value)"}
        onClick={() => void triggerScript(script, parseTriggerValue(value))}>
        <Icon name="zap" size={12} /> Trigger
      </button>
    </div>
  );
}
