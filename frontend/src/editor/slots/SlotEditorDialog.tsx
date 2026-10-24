import { useEffect, useMemo, useState } from "react";
import type { Slot, SlotLink } from "../../api/dynamic";
import { Dialog } from "../../components/Dialog";
import { Icon } from "../../components/Icon";
import { COMPONENT_PREFIX, issuesAbout } from "../../lib/components";
import { removeAt, replaceAt } from "../../lib/probeRules";
import { addInitialInstance } from "../../lib/slots";
import { useCatalogStore } from "../../store/catalogStore";
import { useComponentStore } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { useValidationStore } from "../../store/validationStore";
import { KeyValueEditor } from "../rules/KeyValueEditor";
import { ParamsForm } from "./ParamsForm";

const IDENTIFIER = /^[a-z_][a-z0-9_]*$/;

function LinkRow({ link, ports, index, onChange, onRemove }: {
  link: SlotLink; ports: { name: string; direction: string }[]; index: number;
  onChange: (link: SlotLink) => void; onRemove: () => void;
}) {
  const nodes = useGraphStore((state) => state.graph.nodes);
  const byName = useCatalogStore((state) => state.byName);
  const node = nodes.find((n) => n.id === link.node_id);
  const port = ports.find((p) => p.name === link.port);
  // A component output goes into a sink pad of the element, and the other way round.
  const padDirection = port?.direction === "sink" ? "src" : "sink";
  const pads = (node ? byName[node.factory]?.pads ?? [] : []).filter((pad) => pad.direction === padDirection);
  const listId = `slot-pads-${index}`;
  return (
    <div className="slot-link-row">
      <div className="row wrap">
        <select className="select" value={link.port} aria-label={`Link ${index + 1} port`}
          onChange={(event) => onChange({ ...link, port: event.target.value })}>
          {!port ? <option value={link.port}>{link.port || "port…"}</option> : null}
          {ports.map((p) => <option key={p.name} value={p.name}>{p.name} ({p.direction === "sink" ? "in" : "out"})</option>)}
        </select>
        <span className="faint">{port?.direction === "sink" ? "←" : "→"}</span>
        <select className="select" value={link.node_id} aria-label={`Link ${index + 1} element`}
          onChange={(event) => onChange({ ...link, node_id: event.target.value })}>
          {!node ? <option value={link.node_id}>{link.node_id || "element…"}</option> : null}
          {nodes.map((n) => <option key={n.id} value={n.id}>{n.name}</option>)}
        </select>
        <input className="input input-sm mono" list={listId} value={link.pad} placeholder="sink_%u" aria-label={`Link ${index + 1} pad`}
          onChange={(event) => onChange({ ...link, pad: event.target.value })} />
        <datalist id={listId}>{pads.map((pad) => <option key={pad.name} value={pad.name} />)}</datalist>
        <span className="spacer" />
        <button className="icon-btn" aria-label={`Remove link ${index + 1}`} onClick={onRemove}>
          <Icon name="trash" size={12} />
        </button>
      </div>
      <div className="slot-pad-props">
        <span className="faint">Pad properties per instance (<code>$index</code>, <code>$id</code>):</span>
        <KeyValueEditor value={link.pad_properties} label={`Link ${index + 1} pad properties`}
          keys={["xpos", "ypos", "width", "height", "alpha", "zorder", "volume", "mute"]}
          onChange={(pad_properties) => onChange({ ...link, pad_properties })} />
      </div>
    </div>
  );
}

/** Full slot editor: names, component, links to the static graph, initial instances, limit. */
export function SlotEditorDialog({ slot, onClose }: { slot: Slot; onClose: () => void }) {
  const library = useComponentStore((state) => state.library);
  const summary = useCatalogStore((state) => state.byName[`${COMPONENT_PREFIX}${slot.component}`]);
  const issues = useValidationStore((state) => state.issues);
  const [draft, setDraft] = useState<Slot>(slot);
  const draftSummary = useCatalogStore((state) => state.byName[`${COMPONENT_PREFIX}${draft.component}`]) ?? summary;
  const ports = useMemo(() => draftSummary?.pads.map((pad) => ({ name: pad.name, direction: pad.direction })) ?? [], [draftSummary]);
  const problems = useMemo(() => issuesAbout(issues, "slot", slot.id, slot.name), [issues, slot.id, slot.name]);
  const dirty = JSON.stringify(draft) !== JSON.stringify(slot);
  const nameError = !IDENTIFIER.test(draft.name) || !IDENTIFIER.test(draft.item)
    ? "Names are lowercase identifiers (add_<item>, list_<name>)" : null;

  useEffect(() => {
    if (useComponentStore.getState().libraryState === "idle") void useComponentStore.getState().loadLibrary();
  }, []);

  const save = () => {
    const { name, item, component, links, initial, max_instances } = draft;
    useGraphStore.getState().updateSlot(slot.id, { name, item, component, links, initial, max_instances });
    onClose();
  };
  const close = () => {
    if (!dirty || window.confirm("Discard the changes to this slot?")) onClose();
  };
  const newLink = (): SlotLink => ({ port: ports[0]?.name ?? "", node_id: "", pad: "", pad_properties: {} });

  return (
    <Dialog title={`Slot ${draft.name}`} onClose={close} wide footer={
      <>
        <span className="muted">{nameError ?? `add_${draft.item}() · remove_${draft.item}() · list_${draft.name}()`}</span>
        <span className="spacer" />
        <button className="btn" onClick={close}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={!dirty || Boolean(nameError)}>Save</button>
      </>
    }>
      <div className="slot-editor">
        {problems.length ? (
          <ul className="script-issues">
            {problems.map((issue) => <li key={issue.id} className={`badge ${issue.severity}`}>{issue.message}</li>)}
          </ul>
        ) : null}
        <div className="row wrap">
          <label className="field">
            Slot name (plural)
            <input className="input mono" value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} />
          </label>
          <label className="field">
            Item (singular)
            <input className="input mono" value={draft.item} onChange={(e) => setDraft({ ...draft, item: e.target.value })} />
          </label>
          <label className="field">
            Component
            <select className="select" value={draft.component} onChange={(e) => setDraft({ ...draft, component: e.target.value })}>
              {library.some((c) => c.id === draft.component) ? null : <option value={draft.component}>{draft.component}</option>}
              {library.map((component) => <option key={component.id} value={component.id}>{component.name}</option>)}
            </select>
          </label>
          <label className="field">
            Max instances
            <input className="input" type="number" min={1} value={draft.max_instances ?? ""} placeholder="unlimited"
              onChange={(e) => setDraft({ ...draft, max_instances: e.target.value ? Number(e.target.value) : null })} />
          </label>
        </div>
        <section className="rule-set-section">
          <h3>Links to the pipeline</h3>
          {draft.links.length === 0 ? <p className="muted">An unlinked slot creates isolated instances.</p> : null}
          {draft.links.map((link, index) => (
            <LinkRow key={index} link={link} ports={ports} index={index}
              onChange={(next) => setDraft({ ...draft, links: replaceAt(draft.links, index, next) })}
              onRemove={() => setDraft({ ...draft, links: removeAt(draft.links, index) })} />
          ))}
          <button className="btn btn-sm" onClick={() => setDraft({ ...draft, links: [...draft.links, newLink()] })}>
            <Icon name="plus" size={12} /> Link
          </button>
        </section>
        <section className="rule-set-section">
          <h3>Instances created at start <span className="faint">({draft.initial.length})</span></h3>
          {draft.initial.map((instance, index) => (
            <div key={instance.id} className="instance-card">
              <div className="row">
                <strong className="mono">{instance.id}</strong>
                <span className="spacer" />
                <button className="icon-btn" aria-label={`Remove instance ${instance.id}`}
                  onClick={() => setDraft({ ...draft, initial: removeAt(draft.initial, index) })}>
                  <Icon name="trash" size={12} />
                </button>
              </div>
              <ParamsForm component={draft.component} params={instance.params} label={`Parameters of ${instance.id}`}
                onChange={(params) => setDraft({ ...draft, initial: replaceAt(draft.initial, index, { ...instance, params }) })} />
            </div>
          ))}
          <button className="btn btn-sm" onClick={() => setDraft(addInitialInstance(draft))}>
            <Icon name="plus" size={12} /> Initial instance
          </button>
        </section>
      </div>
    </Dialog>
  );
}
