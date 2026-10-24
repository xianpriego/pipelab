import type { Severity } from "../../api/types";
import { useValidationStore } from "../../store/validationStore";
import { IssueItem } from "./IssueItem";

const GROUPS: [Severity, string][] = [
  ["error", "Errors"],
  ["warning", "Warnings"],
  ["info", "Suggestions"],
];

export function IssuesPanel() {
  const issues = useValidationStore((state) => state.issues);
  const error = useValidationStore((state) => state.error);

  if (error) return <div className="empty-state">Validation unavailable: {error}</div>;
  if (issues.length === 0) {
    return (
      <div className="empty-state">
        <h3>No issues</h3>
        <p>Links, caps and best practices look right. Press ▶ to run the pipeline.</p>
      </div>
    );
  }
  return (
    <div className="issues-panel">
      {GROUPS.map(([severity, label]) => {
        const group = issues.filter((issue) => issue.severity === severity);
        if (group.length === 0) return null;
        return (
          <section key={severity}>
            <h4 className={`issues-group ${severity}`}>{label} ({group.length})</h4>
            {group.map((issue) => <IssueItem key={issue.id} issue={issue} />)}
          </section>
        );
      })}
    </div>
  );
}
