import { useEffect, useMemo, useState } from "react";
import { Icon } from "../../components/Icon";
import { slotsOf } from "../../lib/slots";
import { useComponentStore } from "../../store/componentStore";
import { useGraphStore } from "../../store/graphStore";
import { useUiStore } from "../../store/uiStore";
import { addSlotOn } from "./slotActions";
import { slotNodeId } from "./slotFlow";

/** On mixers, selectors and tees: slots whose instances attach to this element's request pads. */
export function SlotsSection({ nodeId }: { nodeId: string }) {
  const graph = useGraphStore((state) => state.graph);
  const library = useComponentStore((state) => state.library);
  const slots = useMemo(() => slotsOf(graph).filter((slot) => slot.links.some((link) => link.node_id === nodeId)), [graph, nodeId]);
  const [component, setComponent] = useState("");

  useEffect(() => {
    if (useComponentStore.getState().libraryState === "idle") void useComponentStore.getState().loadLibrary();
  }, []);

  const chosen = component || library[0]?.id || "";
  return (
    <section className="inspector-section slots-section">
      <h3>Dynamic slots</h3>
      {slots.length === 0 ? (
        <p className="muted">A slot links N instances of a component to this element, added and removed while running.</p>
      ) : null}
      {slots.map((slot) => (
        <div key={slot.id} className="row">
          <span className="slot-count">×{slot.initial.length}</span>
          <button className="link-btn mono" onClick={() => useUiStore.getState().select([slotNodeId(slot.id)], [])}>
            {slot.name}
          </button>
          <span className="faint">{slot.component}</span>
        </div>
      ))}
      {library.length ? (
        <div className="row wrap">
          <select className="select" value={chosen} aria-label="Component of the new slot" onChange={(e) => setComponent(e.target.value)}>
            {library.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <button className="btn btn-sm" onClick={() => chosen && addSlotOn(nodeId, chosen)} disabled={!chosen}>
            <Icon name="plus" size={12} /> Add slot
          </button>
        </div>
      ) : (
        <p className="faint">Create a component first (palette › Components › New component, or group elements).</p>
      )}
    </section>
  );
}
