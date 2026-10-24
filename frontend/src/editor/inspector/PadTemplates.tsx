import type { PadTemplateInfo } from "../../api/types";

export function PadTemplates({ templates }: { templates: PadTemplateInfo[] }) {
  return (
    <div className="pad-templates">
      {templates.map((template) => (
        <div key={template.name} className="pad-template">
          <div className="row">
            <strong className="mono">{template.name}</strong>
            <span className="badge">{template.direction}</span>
            <span className="badge">{template.presence}</span>
          </div>
          <pre className="caps-block">{template.caps.replace(/; /g, ";\n")}</pre>
        </div>
      ))}
    </div>
  );
}
