import { useMemo, useState } from "react";
import type { ProbeScript, ScriptTarget } from "../../api/types";
import { Icon } from "../../components/Icon";
import { hasTrigger, scriptIssues, scriptsFor } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useValidationStore } from "../../store/validationStore";
import { ProbeRuleList } from "../rules/ProbeRuleList";
import { addKeyframeSwitch } from "../scriptActions";
import { RecipePicker } from "./RecipePicker";
import { ScriptEditorDialog } from "./ScriptEditorDialog";
import { TriggerControl } from "./TriggerControl";

interface ScriptsSectionProps {
  target: ScriptTarget;
  /** Factory of the element (filters recipes); undefined for links. */
  factory?: string;
  /** input/output-selector: offer the one-click "Switch on keyframe" recipe. */
  selector?: boolean;
}

function ScriptRow({ script, running, onEdit }: { script: ProbeScript; running: boolean; onEdit: () => void }) {
  const { updateScript, removeScript } = useGraphStore.getState();
  const issues = useValidationStore((state) => state.issues);
  const problems = useMemo(() => scriptIssues(issues, script), [issues, script]);
  return (
    <div className={`script-row${script.enabled ? "" : " disabled"}`}>
      <div className="row">
        <span className="script-badge" aria-hidden>ƒ</span>
        <button className="link-btn script-name" onClick={onEdit} title="Edit the script">{script.name}</button>
        {problems.length ? (
          <span className={`badge ${problems[0].severity}`} title={problems.map((p) => p.message).join("\n")}>
            {problems.length} issue{problems.length > 1 ? "s" : ""}
          </span>
        ) : null}
        <span className="spacer" />
        <label className="switch" title={script.enabled ? "Enabled" : "Disabled (kept, not run)"}>
          <input type="checkbox" checked={script.enabled} aria-label={`Enable ${script.name}`}
            onChange={(event) => updateScript(script.id, { enabled: event.target.checked })} />
          <span />
        </label>
        <button className="icon-btn" aria-label={`Edit ${script.name}`} title="Edit" onClick={onEdit}>
          <Icon name="file" size={13} />
        </button>
        <button className="icon-btn" aria-label={`Delete ${script.name}`} title="Delete" onClick={() => {
          if (window.confirm(`Delete the script "${script.name}"?`)) removeScript(script.id);
        }}>
          <Icon name="trash" size={13} />
        </button>
      </div>
      {script.enabled && hasTrigger(script.code) ? <TriggerControl script={script} disabled={!running} /> : null}
    </div>
  );
}

/** Probe scripts attached to an element or a link: list, add from recipes, edit, trigger. */
export function ScriptsSection({ target, factory, selector }: ScriptsSectionProps) {
  const graph = useGraphStore((state) => state.graph);
  const scripts = useMemo(() => scriptsFor(graph, target.kind, target.id), [graph, target.kind, target.id]);
  const running = useRuntimeStore((state) => isActive(state.state));
  const [picking, setPicking] = useState(false);
  const [editing, setEditing] = useState<string | null>(null);
  const edited = scripts.find((script) => script.id === editing);

  return (
    <section className="inspector-section scripts-section">
      <h3>Probes &amp; scripts</h3>
      <h4 className="subhead">No-code probes</h4>
      <ProbeRuleList target={target} factory={factory} />
      <h4 className="subhead">Python scripts</h4>
      {scripts.length === 0 && !picking ? (
        <p className="muted">
          Python run on {target.kind === "edge" ? "every buffer and event of this link" : "this element's pads"}:
          drop data, switch on keyframes, request key units, log…
        </p>
      ) : null}
      {scripts.map((script) => (
        <ScriptRow key={script.id} script={script} running={running} onEdit={() => setEditing(script.id)} />
      ))}
      {picking ? (
        <RecipePicker target={target} factory={factory} onCancel={() => setPicking(false)}
          onAdded={(script) => { setPicking(false); setEditing(script.id); }} />
      ) : (
        <div className="row wrap">
          {selector && scripts.length === 0 ? (
            <button className="btn btn-sm btn-primary" title="Selecting another pad waits for its next keyframe"
              aria-label="Add the switch on keyframe script"
              onClick={() => void addKeyframeSwitch(target.id)}>
              <Icon name="zap" size={12} /> Switch on keyframe
            </button>
          ) : null}
          <button className="btn btn-sm" onClick={() => setPicking(true)}>
            <Icon name="plus" size={12} /> Add script
          </button>
        </div>
      )}
      {edited ? <ScriptEditorDialog script={edited} onClose={() => setEditing(null)} /> : null}
    </section>
  );
}
