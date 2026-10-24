import { useMemo, useState } from "react";
import type { ApiFunction, FunctionParam, ParamType } from "../../api/dynamic";
import { Dialog } from "../../components/Dialog";
import { Icon } from "../../components/Icon";
import { functionsOf, isIdentifier } from "../../lib/apiFunctions";
import { issuesAbout } from "../../lib/components";
import { removeAt, replaceAt } from "../../lib/probeRules";
import { formatValue, parseValue } from "../../lib/valueRefs";
import { useGraphStore } from "../../store/graphStore";
import { useValidationStore } from "../../store/validationStore";
import { ActionList } from "../rules/ActionList";
import { RuleEditorCtx } from "../rules/editorContext";
import { useEditorContext } from "../rules/useEditorContext";

const TYPES: ParamType[] = ["string", "int", "float", "bool"];
const NO_VARIABLES = {};

function ParamRow({ param, index, onChange, onRemove }: {
  param: FunctionParam; index: number; onChange: (param: FunctionParam) => void; onRemove: () => void;
}) {
  return (
    <div className="row param-row">
      <input className="input input-sm mono" value={param.name} placeholder="name" aria-label={`Parameter ${index + 1} name`}
        onChange={(event) => onChange({ ...param, name: event.target.value })} />
      <select className="select" value={param.type} aria-label={`Parameter ${index + 1} type`}
        onChange={(event) => onChange({ ...param, type: event.target.value as ParamType })}>
        {TYPES.map((type) => <option key={type} value={type}>{type}</option>)}
      </select>
      <input className="input input-sm mono" value={formatValue(param.default ?? null)} placeholder="default (required if empty)"
        aria-label={`Parameter ${index + 1} default`}
        onChange={(event) => onChange({ ...param, default: event.target.value === "" ? null : parseValue(event.target.value) })} />
      <input className="input input-sm grow" value={param.description ?? ""} placeholder="description"
        aria-label={`Parameter ${index + 1} description`} onChange={(event) => onChange({ ...param, description: event.target.value })} />
      <button className="icon-btn" aria-label={`Remove parameter ${index + 1}`} onClick={onRemove}>
        <Icon name="trash" size={12} />
      </button>
    </div>
  );
}

/** Custom pipeline API function: name, typed parameters ($name in actions) and actions. */
export function FunctionEditorDialog({ fn, isNew, onClose }: { fn: ApiFunction; isNew: boolean; onClose: () => void }) {
  const graph = useGraphStore((state) => state.graph);
  const issues = useValidationStore((state) => state.issues);
  const [draft, setDraft] = useState<ApiFunction>(fn);
  const paramNames = useMemo(() => draft.params.map((p) => p.name).filter(Boolean), [draft.params]);
  const ctx = useEditorContext(NO_VARIABLES, paramNames);
  const problems = useMemo(() => (isNew ? [] : issuesAbout(issues, "function", fn.name, fn.name)), [issues, fn.name, isNew]);
  const taken = functionsOf(graph).some((other) => other.name === draft.name && other.name !== fn.name);
  const error = !isIdentifier(draft.name) ? "The name is a lowercase identifier (snake_case)"
    : taken ? `"${draft.name}" already exists`
      : draft.params.some((p) => !isIdentifier(p.name)) ? "Parameter names are lowercase identifiers"
        : new Set(paramNames).size !== paramNames.length ? "Parameter names must be unique" : null;

  const save = () => {
    const store = useGraphStore.getState();
    if (isNew) store.addFunction(draft);
    else store.updateFunction(fn.name, draft);
    onClose();
  };
  const close = () => {
    if (JSON.stringify(draft) === JSON.stringify(fn) || window.confirm("Discard the changes to this function?")) onClose();
  };

  return (
    <Dialog title={isNew ? "New API function" : `Function ${fn.name}`} onClose={close} wide footer={
      <>
        <span className="muted">{error ?? "Callable from the API panel, other rules (call) and the exported code"}</span>
        <span className="spacer" />
        <button className="btn" onClick={close}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={Boolean(error)}>{isNew ? "Add function" : "Save"}</button>
      </>
    }>
      <RuleEditorCtx.Provider value={ctx}>
        <div className="rule-set-editor">
          {problems.length ? (
            <ul className="script-issues">
              {problems.map((issue) => <li key={issue.id} className={`badge ${issue.severity}`}>{issue.message}</li>)}
            </ul>
          ) : null}
          <div className="row wrap">
            <label className="field">
              Name
              <input className="input mono" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </label>
            <label className="field grow">
              Description
              <input className="input" value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} />
            </label>
          </div>
          <section className="rule-set-section">
            <h3>Parameters <span className="faint">— use them as <code>$name</code> in the actions</span></h3>
            {draft.params.map((param, index) => (
              <ParamRow key={index} param={param} index={index}
                onChange={(next) => setDraft({ ...draft, params: replaceAt(draft.params, index, next) })}
                onRemove={() => setDraft({ ...draft, params: removeAt(draft.params, index) })} />
            ))}
            <button className="btn btn-sm" onClick={() => setDraft({
              ...draft, params: [...draft.params, { name: `arg${draft.params.length + 1}`, type: "string", default: null, description: "" }],
            })}>
              <Icon name="plus" size={12} /> Parameter
            </button>
          </section>
          <section className="rule-set-section">
            <h3>Actions <span className="faint">— run in order</span></h3>
            <ActionList actions={draft.actions} label={draft.name || "Function"}
              onChange={(actions) => setDraft({ ...draft, actions })} />
          </section>
        </div>
      </RuleEditorCtx.Provider>
    </Dialog>
  );
}
