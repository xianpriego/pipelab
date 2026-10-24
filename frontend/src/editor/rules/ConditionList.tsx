import type { Condition } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { blankCondition, removeAt, replaceAt } from "../../lib/probeRules";
import { useRuleEditor } from "./editorContext";
import { SpecForm } from "./SpecForm";

interface ConditionListProps {
  conditions: Condition[];
  onChange: (conditions: Condition[]) => void;
  label: string;
}

/** Conditions that must all hold; each can be negated. */
export function ConditionList({ conditions, onChange, label }: ConditionListProps) {
  const { schema } = useRuleEditor();
  return (
    <div className="item-list">
      {conditions.length === 0 ? <span className="faint">Always</span> : null}
      {conditions.map((condition, index) => (
        <div key={`${index}-${condition.type}`} className="item-row">
          <span className="item-index faint">{index === 0 ? "if" : "and"}</span>
          <label className={`negate-toggle${condition.negate ? " on" : ""}`} title="Invert the condition">
            <input type="checkbox" checked={condition.negate === true} aria-label={`Negate ${label} condition ${index + 1}`}
              onChange={(event) => onChange(replaceAt(conditions, index, { ...condition, negate: event.target.checked }))} />
            not
          </label>
          <SpecForm specs={schema.conditions} item={condition} label={`${label} condition ${index + 1}`}
            onChange={(next) => onChange(replaceAt(conditions, index, { ...next, negate: condition.negate }))} />
          <span className="item-tools">
            <button type="button" className="icon-btn" aria-label={`Remove ${label} condition ${index + 1}`}
              onClick={() => onChange(removeAt(conditions, index))}>
              <Icon name="trash" size={12} />
            </button>
          </span>
        </div>
      ))}
      <button type="button" className="btn btn-sm add-item" onClick={() => onChange([...conditions, blankCondition("keyframe")])}>
        <Icon name="plus" size={12} /> Condition
      </button>
    </div>
  );
}
