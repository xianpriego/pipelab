import { useMemo, useState } from "react";
import type { ProbeRuleSet } from "../../api/dynamic";
import { Dialog } from "../../components/Dialog";
import { Icon } from "../../components/Icon";
import { issuesAbout } from "../../lib/components";
import { newId } from "../../lib/ids";
import { newRule, removeAt, replaceAt } from "../../lib/probeRules";
import { usedPads } from "../../lib/pads";
import { targetLabel } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useValidationStore } from "../../store/validationStore";
import { RuleEditorCtx } from "./editorContext";
import { RuleCard } from "./RuleCard";
import { useEditorContext } from "./useEditorContext";
import { VariablesEditor } from "./VariablesEditor";

interface RuleSetEditorDialogProps {
  probe: ProbeRuleSet;
  onClose: () => void;
}

/** Full editor of a no-code probe: target pads, variables and When/If/Then rules. */
export function RuleSetEditorDialog({ probe, onClose }: RuleSetEditorDialogProps) {
  const graph = useGraphStore((state) => state.graph);
  const issues = useValidationStore((state) => state.issues);
  const [draft, setDraft] = useState<ProbeRuleSet>(probe);
  const ctx = useEditorContext(draft.variables);
  const problems = useMemo(() => issuesAbout(issues, "probe", probe.id, probe.name), [issues, probe.id, probe.name]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(probe);
  const pads = draft.target.kind === "node" ? usedPads(draft.target.id, graph.edges, "sink")
    .concat(usedPads(draft.target.id, graph.edges, "src")) : [];

  const save = () => {
    useGraphStore.getState().updateProbe(probe.id, {
      name: draft.name, enabled: draft.enabled, target: draft.target, variables: draft.variables, rules: draft.rules,
    });
    onClose();
  };
  const close = () => {
    if (!dirty || window.confirm("Discard the changes to this probe?")) onClose();
  };

  return (
    <Dialog title={`Probe on ${targetLabel(graph, draft.target)}`} onClose={close} wide footer={
      <>
        <span className="muted">{draft.rules.length} rule{draft.rules.length === 1 ? "" : "s"}</span>
        <span className="spacer" />
        <button className="btn" onClick={close}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={!dirty}>Save</button>
      </>
    }>
      <RuleEditorCtx.Provider value={ctx}>
        <div className="rule-set-editor">
          <div className="row wrap rule-set-head">
            <label className="field grow">
              Name
              <input className="input" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
            </label>
            {draft.target.kind === "node" ? (
              <label className="field">
                Watched pads
                <select className="select" value={draft.target.pad ?? ""} aria-label="Watched pads"
                  onChange={(e) => setDraft({ ...draft, target: { ...draft.target, pad: e.target.value || null } })}>
                  <option value="">All sink pads</option>
                  {pads.map((pad) => <option key={pad} value={pad}>{pad}</option>)}
                </select>
              </label>
            ) : null}
            <label className="row nowrap">
              <span className="switch">
                <input type="checkbox" checked={draft.enabled} aria-label="Probe enabled"
                  onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })} />
                <span />
              </span>
              Enabled
            </label>
          </div>
          {problems.length ? (
            <ul className="script-issues">
              {problems.map((issue) => <li key={issue.id} className={`badge ${issue.severity}`}>{issue.message}</li>)}
            </ul>
          ) : null}
          <section className="rule-set-section">
            <h3>Variables</h3>
            <VariablesEditor variables={draft.variables} onChange={(variables) => setDraft({ ...draft, variables })} />
          </section>
          <section className="rule-set-section">
            <h3>Rules <span className="faint">— evaluated in order for each trigger</span></h3>
            {draft.rules.map((rule, index) => (
              <RuleCard key={rule.id} rule={rule} index={index}
                onChange={(next) => setDraft({ ...draft, rules: replaceAt(draft.rules, index, next) })}
                onRemove={() => setDraft({ ...draft, rules: removeAt(draft.rules, index) })}
                onDuplicate={() => setDraft({
                  ...draft, rules: [...draft.rules.slice(0, index + 1), { ...rule, id: newId("r") }, ...draft.rules.slice(index + 1)],
                })} />
            ))}
            <button className="btn btn-sm" onClick={() => setDraft({ ...draft, rules: [...draft.rules, newRule()] })}>
              <Icon name="plus" size={12} /> Rule
            </button>
          </section>
        </div>
      </RuleEditorCtx.Provider>
    </Dialog>
  );
}
