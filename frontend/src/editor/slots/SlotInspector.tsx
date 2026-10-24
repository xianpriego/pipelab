import { useEffect, useState } from "react";
import type { Slot, SlotInstance } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { issuesAbout } from "../../lib/components";
import { formatValue } from "../../lib/valueRefs";
import { useGraphStore } from "../../store/graphStore";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";
import { useValidationStore } from "../../store/validationStore";
import { AddInstanceDialog } from "./AddInstanceDialog";
import { refreshInstances, removeLiveInstance, restartLiveInstance } from "./slotActions";
import { SlotEditorDialog } from "./SlotEditorDialog";

function paramsText(instance: SlotInstance): string {
  return Object.entries(instance.params).map(([key, value]) => `${key}=${formatValue(value)}`).join(" ");
}

function LiveInstances({ slot }: { slot: Slot }) {
  const live = useRuntimeStore((state) => state.instances[slot.id]);
  const [adding, setAdding] = useState(false);
  const instances = live ?? [];
  const full = Boolean(slot.max_instances && instances.length >= slot.max_instances);

  useEffect(() => {
    void refreshInstances();
  }, []);

  return (
    <section className="inspector-section">
      <div className="row">
        <h3>Live instances <span className="faint">({instances.length})</span></h3>
        <span className="spacer" />
        <button className="btn btn-sm btn-primary" onClick={() => setAdding(true)} disabled={full}
          title={full ? "The slot is full" : `add_${slot.item}(…)`}>
          <Icon name="plus" size={12} /> Add
        </button>
      </div>
      <ul className="instance-list" aria-label={`Live instances of ${slot.name}`}>
        {instances.map((instance) => (
          <li key={instance.id} className="row">
            <strong className="mono">{instance.id}</strong>
            <span className="faint mono instance-params">{paramsText(instance)}</span>
            <span className="spacer" />
            <button className="icon-btn" aria-label={`Restart ${instance.id}`} title="Restart (same parameters)"
              onClick={() => void restartLiveInstance(slot, instance.id)}>
              <Icon name="refresh" size={12} />
            </button>
            <button className="icon-btn" aria-label={`Remove ${instance.id}`} title="Remove while running"
              onClick={() => void removeLiveInstance(slot, instance.id)}>
              <Icon name="trash" size={12} />
            </button>
          </li>
        ))}
      </ul>
      {instances.length === 0 ? <p className="muted">No instance running.</p> : null}
      {adding ? <AddInstanceDialog slot={slot} onClose={() => setAdding(false)} /> : null}
    </section>
  );
}

/** Inspector of a selected slot node. */
export function SlotInspector({ slotId }: { slotId: string }) {
  const slot = useGraphStore((state) => state.graph.slots?.find((s) => s.id === slotId));
  const nodes = useGraphStore((state) => state.graph.nodes);
  const running = useRuntimeStore((state) => isActive(state.state));
  const issues = useValidationStore((state) => state.issues);
  const [editing, setEditing] = useState(false);
  if (!slot) return null;
  const problems = issuesAbout(issues, "slot", slot.id, slot.name);
  const nodeName = (id: string) => nodes.find((n) => n.id === id)?.name ?? `${id} (missing)`;

  return (
    <div className="inspector-scroll">
      <div className="inspector-section">
        <div className="row">
          <h3 className="mono">{slot.name}</h3>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={() => setEditing(true)}>Edit slot…</button>
        </div>
        <p className="muted">
          Instances of <strong>{slot.component}</strong> added and removed while running with
          <code> add_{slot.item}()</code>, <code>remove_{slot.item}(id)</code>, <code>restart_{slot.item}(id)</code>,
          <code> list_{slot.name}()</code>{slot.max_instances ? ` — at most ${slot.max_instances}` : ""}.
        </p>
        {problems.map((issue) => <div key={issue.id} className={`badge ${issue.severity}`}>{issue.message}</div>)}
        <ul className="target-list">
          {slot.links.map((link, index) => (
            <li key={index} className="mono">{link.port} ⇢ {nodeName(link.node_id)}.{link.pad}</li>
          ))}
        </ul>
      </div>
      {running ? <LiveInstances slot={slot} /> : (
        <div className="inspector-section">
          <h3>Instances at start <span className="faint">({slot.initial.length})</span></h3>
          <ul className="instance-list">
            {slot.initial.map((instance) => (
              <li key={instance.id} className="row">
                <strong className="mono">{instance.id}</strong>
                <span className="faint mono instance-params">{paramsText(instance)}</span>
              </li>
            ))}
          </ul>
          <p className="faint">Run the pipeline to add, remove and restart instances live.</p>
        </div>
      )}
      <div className="inspector-section">
        <button className="btn btn-danger" onClick={() => {
          useGraphStore.getState().removeSlot(slot.id);
          useUiStore.getState().select([], []);
        }}>
          Delete slot
        </button>
      </div>
      {editing ? <SlotEditorDialog slot={slot} onClose={() => setEditing(false)} /> : null}
    </div>
  );
}
