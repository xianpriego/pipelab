import { useMemo, useState } from "react";
import type { ProbeRuleSet, ProbeTarget } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { issuesAbout } from "../../lib/components";
import { probesFor, ruleSummary } from "../../lib/probeRules";
import { useGraphStore } from "../../store/graphStore";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useValidationStore } from "../../store/validationStore";
import { ProbeTemplatePicker } from "./ProbeTemplatePicker";
import { RuleSetEditorDialog } from "./RuleSetEditorDialog";
import { SignalControl } from "./SignalControl";

function ProbeRow({ probe, running, onEdit }: { probe: ProbeRuleSet; running: boolean; onEdit: () => void }) {
  const { updateProbe, removeProbe } = useGraphStore.getState();
  const issues = useValidationStore((state) => state.issues);
  const problems = useMemo(() => issuesAbout(issues, "probe", probe.id, probe.name), [issues, probe.id, probe.name]);
  return (
    <div className={`script-row probe-row-item${probe.enabled ? "" : " disabled"}`}>
      <div className="row">
        <span className="probe-badge" aria-hidden>◉</span>
        <button className="link-btn script-name" onClick={onEdit} title={probe.rules.map(ruleSummary).join("\n")}>
          {probe.name}
        </button>
        <span className="faint">{probe.rules.length} rule{probe.rules.length === 1 ? "" : "s"}</span>
        {problems.length ? (
          <span className={`badge ${problems[0].severity}`} title={problems.map((p) => p.message).join("\n")}>
            {problems.length} issue{problems.length > 1 ? "s" : ""}
          </span>
        ) : null}
        <span className="spacer" />
        <label className="switch" title={probe.enabled ? "Enabled" : "Disabled"}>
          <input type="checkbox" checked={probe.enabled} aria-label={`Enable ${probe.name}`}
            onChange={(event) => updateProbe(probe.id, { enabled: event.target.checked })} />
          <span />
        </label>
        <button className="icon-btn" aria-label={`Edit ${probe.name}`} title="Edit" onClick={onEdit}>
          <Icon name="file" size={13} />
        </button>
        <button className="icon-btn" aria-label={`Delete ${probe.name}`} title="Delete" onClick={() => {
          if (window.confirm(`Delete the probe "${probe.name}"?`)) removeProbe(probe.id);
        }}>
          <Icon name="trash" size={13} />
        </button>
      </div>
      {probe.enabled ? <SignalControl probe={probe} disabled={!running} /> : null}
    </div>
  );
}

/** No-code probes attached to an element or a link: list, add from templates, edit, signal. */
export function ProbeRuleList({ target, factory }: { target: ProbeTarget; factory?: string }) {
  const graph = useGraphStore((state) => state.graph);
  const probes = useMemo(() => probesFor(graph, target.kind, target.id), [graph, target.kind, target.id]);
  const running = useRuntimeStore((state) => isActive(state.state));
  const [picking, setPicking] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const edited = probes.find((probe) => probe.id === editing);

  return (
    <div className="probe-rule-list">
      {probes.map((probe) => (
        <ProbeRow key={probe.id} probe={probe} running={running} onEdit={() => setEditing(probe.id)} />
      ))}
      {picking ? (
        <ProbeTemplatePicker target={target} factory={factory} onCancel={() => setPicking(false)}
          onAdded={(probe) => { setPicking(false); setEditing(probe.id); }} />
      ) : (
        <button className="btn btn-sm" onClick={() => setPicking(true)} title="When … if … then … rules, no code">
          <Icon name="plus" size={12} /> Add probe
        </button>
      )}
      {edited ? <RuleSetEditorDialog probe={edited} onClose={() => setEditing(null)} /> : null}
    </div>
  );
}
