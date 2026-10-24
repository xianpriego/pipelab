import { useState, type FormEvent } from "react";
import type { CallResult, FunctionParam } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { callArgs, signature } from "../../lib/apiFunctions";
import { formatValue } from "../../lib/valueRefs";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { callFunction, refreshInstances } from "../slots/slotActions";

interface CallFormProps {
  name: string;
  params: FunctionParam[];
  returns?: string;
}

function ArgInput({ param, value, onChange }: { param: FunctionParam; value: string | undefined; onChange: (text: string) => void }) {
  const label = `Argument ${param.name}`;
  if (param.type === "bool") {
    const checked = value === undefined ? param.default === true : value === "true";
    return (
      <input type="checkbox" checked={checked} aria-label={label}
        onChange={(event) => onChange(event.target.checked ? "true" : "false")} />
    );
  }
  return (
    <input className="input input-sm mono" aria-label={label} value={value ?? ""}
      type={param.type === "string" ? "text" : "number"} step={param.type === "float" ? "any" : 1}
      placeholder={param.default === undefined || param.default === null ? param.type : formatValue(param.default)}
      onChange={(event) => onChange(event.target.value)} />
  );
}

/** Typed arguments of a pipeline API function and a Call button (while running). */
export function CallForm({ name, params, returns = "" }: CallFormProps) {
  const running = useRuntimeStore((state) => isActive(state.state));
  const [texts, setTexts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CallResult | null>(null);

  const call = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    const outcome = await callFunction(name, callArgs(params, texts));
    setBusy(false);
    setResult(outcome);
    if (outcome.ok) void refreshInstances();
  };

  return (
    <form className="call-form" onSubmit={(event) => void call(event)} aria-label={`Call ${name}`}>
      <div className="mono call-signature">{signature(name, params, returns)}</div>
      {params.length ? (
        <div className="call-args">
          {params.map((param) => (
            <label key={param.name} className="call-arg" title={param.description}>
              <span className="mono">{param.name}</span>
              <span className="faint">{param.type}</span>
              <ArgInput param={param} value={texts[param.name]}
                onChange={(text) => setTexts((current) => ({ ...current, [param.name]: text }))} />
            </label>
          ))}
        </div>
      ) : null}
      <div className="row">
        <button className="btn btn-sm btn-primary" type="submit" disabled={!running || busy}
          title={running ? `POST /runtime/call ${name}` : "Run the pipeline to call its API"}>
          {busy ? <span className="spinner" /> : <Icon name="play" size={11} />} Call
        </button>
        {!running ? <span className="faint">Available while the pipeline runs.</span> : null}
      </div>
      {result ? (
        <div className={`call-result ${result.ok ? "ok" : "failed"}`} role="status">
          {result.ok ? (
            <><strong>→</strong> <code>{result.result === undefined ? "None" : JSON.stringify(result.result)}</code></>
          ) : (
            <><strong>Error:</strong> {result.error ?? "the call failed"}</>
          )}
        </div>
      ) : null}
    </form>
  );
}
