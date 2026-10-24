import { useState, type DragEvent } from "react";
import type { Action } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { blankAction, moveItem, removeAt, replaceAt } from "../../lib/probeRules";
import { useRuleEditor } from "./editorContext";
import { SpecForm } from "./SpecForm";

interface ActionListProps {
  actions: Action[];
  onChange: (actions: Action[]) => void;
  /** Prefix of accessible names ("Rule 1"). */
  label: string;
}

/** Ordered actions: drag (or ↑/↓) to reorder, they run top to bottom. */
export function ActionList({ actions, onChange, label }: ActionListProps) {
  const { schema } = useRuleEditor();
  const [dragged, setDragged] = useState<number | null>(null);

  const onDrop = (event: DragEvent, index: number) => {
    event.preventDefault();
    if (dragged !== null) onChange(moveItem(actions, dragged, index));
    setDragged(null);
  };

  return (
    <div className="item-list">
      {actions.map((action, index) => (
        // Actions have no ids: the index is their identity inside one render.
        <div key={`${index}-${action.type}`} className={`item-row${dragged === index ? " dragging" : ""}`} draggable
          onDragStart={() => setDragged(index)} onDragEnd={() => setDragged(null)}
          onDragOver={(event) => event.preventDefault()} onDrop={(event) => onDrop(event, index)}>
          <span className="drag-grip" title="Drag to reorder" aria-hidden>⋮⋮</span>
          <span className="item-index faint">{index + 1}</span>
          <SpecForm specs={schema.actions} item={action} label={`${label} action ${index + 1}`}
            onChange={(next) => onChange(replaceAt(actions, index, next))} />
          <span className="item-tools">
            <button type="button" className="icon-btn" aria-label={`Move ${label} action ${index + 1} up`}
              disabled={index === 0} onClick={() => onChange(moveItem(actions, index, index - 1))}>
              <Icon name="chevronUp" size={12} />
            </button>
            <button type="button" className="icon-btn" aria-label={`Move ${label} action ${index + 1} down`}
              disabled={index === actions.length - 1} onClick={() => onChange(moveItem(actions, index, index + 1))}>
              <Icon name="chevronDown" size={12} />
            </button>
            <button type="button" className="icon-btn" aria-label={`Remove ${label} action ${index + 1}`}
              onClick={() => onChange(removeAt(actions, index))}>
              <Icon name="trash" size={12} />
            </button>
          </span>
        </div>
      ))}
      <button type="button" className="btn btn-sm add-item" onClick={() => onChange([...actions, blankAction("log")])}>
        <Icon name="plus" size={12} /> Action
      </button>
    </div>
  );
}
