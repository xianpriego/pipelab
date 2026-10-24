import type { ProbeRule, Trigger } from "../../api/dynamic";
import { Icon } from "../../components/Icon";
import { ActionList } from "./ActionList";
import { ConditionList } from "./ConditionList";
import { useRuleEditor } from "./editorContext";
import { SpecForm } from "./SpecForm";

interface RuleCardProps {
  rule: ProbeRule;
  index: number;
  onChange: (rule: ProbeRule) => void;
  onRemove: () => void;
  onDuplicate: () => void;
}

/** "When … · If … · Then …" card of one rule. */
export function RuleCard({ rule, index, onChange, onRemove, onDuplicate }: RuleCardProps) {
  const { schema } = useRuleEditor();
  const label = `Rule ${index + 1}`;
  return (
    <section className="rule-card" aria-label={label}>
      <header className="rule-card-head">
        <span className="rule-number">{index + 1}</span>
        <span className="spacer" />
        <button type="button" className="icon-btn" aria-label={`Duplicate ${label}`} title="Duplicate" onClick={onDuplicate}>
          <Icon name="copy" size={13} />
        </button>
        <button type="button" className="icon-btn" aria-label={`Delete ${label}`} title="Delete" onClick={onRemove}>
          <Icon name="trash" size={13} />
        </button>
      </header>
      <div className="rule-part">
        <span className="rule-part-label when">When</span>
        <SpecForm<Trigger> specs={schema.triggers} item={rule.when} label={`${label} trigger`}
          onChange={(when) => onChange({ ...rule, when })} />
      </div>
      <div className="rule-part">
        <span className="rule-part-label if">If</span>
        <ConditionList conditions={rule.conditions} label={label} onChange={(conditions) => onChange({ ...rule, conditions })} />
      </div>
      <div className="rule-part">
        <span className="rule-part-label then">Then</span>
        <ActionList actions={rule.actions} label={label} onChange={(actions) => onChange({ ...rule, actions })} />
      </div>
    </section>
  );
}
