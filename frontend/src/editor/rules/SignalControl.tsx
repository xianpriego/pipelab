import { useState } from "react";
import type { ProbeRuleSet } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { signalNames } from "../../lib/probeRules";
import { parseValue } from "../../lib/valueRefs";
import { sendSignal } from "./probeActions";

/** One button per signal a running probe reacts to, with an optional value. */
export function SignalControl({ probe, disabled }: { probe: ProbeRuleSet; disabled: boolean }) {
  const names = signalNames(probe);
  const [value, setValue] = useState("");
  if (names.length === 0) return null;
  return (
    <div className="row wrap signal-control">
      <input className="input input-sm" placeholder="value (optional)" value={value} aria-label={`Signal value for ${probe.name}`}
        onChange={(event) => setValue(event.target.value)} disabled={disabled} />
      {names.map((name) => (
        <button key={name} className="btn btn-sm" disabled={disabled} aria-label={`Send signal ${name} to ${probe.name}`}
          title={disabled ? "Available while running" : `Fire the "${name}" rules`}
          onClick={() => void sendSignal(probe, name, parseValue(value))}>
          <Icon name="bolt" size={11} /> {name}
        </button>
      ))}
    </div>
  );
}
