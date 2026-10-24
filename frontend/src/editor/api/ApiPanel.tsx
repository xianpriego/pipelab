import { useMemo, useState, type ReactNode } from "react";
import type { ApiFunction, FunctionParam, Slot } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { useElementDetails } from "../../hooks/useElementDetails";
import { createFunction, functionsOf, signature } from "../../lib/apiFunctions";
import { COMPONENT_PREFIX } from "../../lib/components";
import { builtinFunctions, slotsOf } from "../../lib/slots";
import { projectGraph, useGraphStore } from "../../store/graphStore";
import { CallForm } from "./CallForm";
import { FunctionEditorDialog } from "./FunctionEditorDialog";

interface Selected {
  name: string;
  params: FunctionParam[];
  returns: string;
}

function FunctionRow({ name, params, returns, description, active, onSelect, children }: Selected & {
  description: string; active: boolean; onSelect: () => void; children?: ReactNode;
}) {
  return (
    <div className={`api-row${active ? " active" : ""}`}>
      <button className="link-btn mono api-signature" onClick={onSelect} title={description || undefined}>
        {signature(name, params, returns)}
      </button>
      <span className="spacer" />
      {children}
    </div>
  );
}

function SlotFunctions({ slot, selected, onSelect }: { slot: Slot; selected: string | null; onSelect: (fn: Selected) => void }) {
  const details = useElementDetails(`${COMPONENT_PREFIX}${slot.component}`);
  const fns = useMemo(() => builtinFunctions(slot, details?.properties ?? []), [slot, details]);
  return (
    <div className="api-group">
      <div className="api-group-title faint">slot <strong className="mono">{slot.name}</strong> · {slot.component}</div>
      {fns.map((fn) => (
        <FunctionRow key={fn.name} {...fn} active={selected === fn.name} onSelect={() => onSelect(fn)} />
      ))}
    </div>
  );
}

/** The pipeline's API: built-in slot functions and custom ones, with a call form. */
export function ApiPanel() {
  // The API belongs to the project, even while a component is open on the canvas.
  const graph = useGraphStore((state) => projectGraph(state));
  const inComponent = useGraphStore((state) => state.scopes.length > 0);
  const slots = slotsOf(graph);
  const functions = functionsOf(graph);
  const [selected, setSelected] = useState<Selected | null>(null);
  const [editing, setEditing] = useState<{ fn: ApiFunction; isNew: boolean } | null>(null);
  const current = selected && (functions.find((fn) => fn.name === selected.name)
    ? { ...selected, params: functions.find((fn) => fn.name === selected.name)?.params ?? [] } : selected);

  return (
    <div className="api-panel">
      <div className="api-list">
        {slots.length === 0 ? (
          <div className="api-group">
            <span className="faint">Slot functions</span>
            <p className="muted">
              <code>add_&lt;item&gt;()</code>, <code>remove_&lt;item&gt;()</code>… appear here when the pipeline has a slot: select a
              mixer, selector or tee (e.g. an input-selector), pick a component under <strong>Dynamic slots</strong> and press{" "}
              <strong>Add slot</strong>.
            </p>
          </div>
        ) : null}
        {slots.map((slot) => (
          <SlotFunctions key={slot.id} slot={slot} selected={current?.name ?? null} onSelect={setSelected} />
        ))}
        <div className="api-group">
          <div className="row api-group-title">
            <span className="faint">Custom functions</span>
            <span className="spacer" />
            <button className="btn btn-sm" disabled={inComponent} title={inComponent ? "Close the component first" : undefined}
              onClick={() => setEditing({ fn: createFunction(functions.map((fn) => fn.name)), isNew: true })}>
              <Icon name="plus" size={12} /> New function
            </button>
          </div>
          {functions.length === 0 ? (
            <p className="muted">Functions run a list of actions (set properties, add instances, post messages…) when called
              from here, from probe rules or from the exported Rust/Python code.</p>
          ) : null}
          {functions.map((fn) => (
            <FunctionRow key={fn.name} name={fn.name} params={fn.params} returns="" description={fn.description}
              active={current?.name === fn.name} onSelect={() => setSelected({ name: fn.name, params: fn.params, returns: "" })}>
              <button className="icon-btn" aria-label={`Edit ${fn.name}`} disabled={inComponent}
                onClick={() => setEditing({ fn, isNew: false })}>
                <Icon name="file" size={12} />
              </button>
              <button className="icon-btn" aria-label={`Delete ${fn.name}`} disabled={inComponent} onClick={() => {
                if (window.confirm(`Delete the function "${fn.name}"?`)) useGraphStore.getState().removeFunction(fn.name);
              }}>
                <Icon name="trash" size={12} />
              </button>
            </FunctionRow>
          ))}
        </div>
      </div>
      <div className="api-call">
        {current ? <CallForm key={current.name} name={current.name} params={current.params} returns={current.returns} /> : (
          <div className="empty-state">Pick a function to call it on the running pipeline.</div>
        )}
      </div>
      {editing ? <FunctionEditorDialog fn={editing.fn} isNew={editing.isNew} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}
