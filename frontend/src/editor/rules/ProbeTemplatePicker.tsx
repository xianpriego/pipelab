import type { ProbeRuleSet, ProbeTarget } from "../../api/dynamic";
import { templatesFor } from "../../lib/probeTemplates";
import { addProbeFromTemplate } from "./probeActions";

interface ProbeTemplatePickerProps {
  target: ProbeTarget;
  factory?: string;
  onCancel: () => void;
  onAdded: (probe: ProbeRuleSet) => void;
}

/** Templates to start a no-code probe from. */
export function ProbeTemplatePicker({ target, factory, onCancel, onAdded }: ProbeTemplatePickerProps) {
  const templates = templatesFor(target.kind, factory);
  return (
    <div className="recipe-picker" role="list" aria-label="Probe templates">
      {templates.map((template) => (
        <button key={template.id} type="button" className="recipe-option" role="listitem"
          onClick={() => onAdded(addProbeFromTemplate(template, target))}>
          <strong>{template.name}</strong>
          <span className="muted">{template.description}</span>
        </button>
      ))}
      <button className="btn btn-sm" onClick={onCancel}>Cancel</button>
    </div>
  );
}
