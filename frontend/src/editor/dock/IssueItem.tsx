import type { Issue } from "../../api/types";
import { Icon } from "../../components/Icon";
import { useGraphStore } from "../../store/graphStore";
import { useUiStore } from "../../store/uiStore";
import { applyFix } from "../actions";

const ICON = { error: "error", warning: "warning", info: "info" } as const;

export function IssueItem({ issue, compact = false }: { issue: Issue; compact?: boolean }) {
  const nodes = useGraphStore((state) => state.graph.nodes);
  const select = useUiStore((state) => state.select);
  const requestFocus = useUiStore((state) => state.requestFocus);
  const names = issue.node_ids
    .map((id) => nodes.find((node) => node.id === id))
    .filter((node) => node !== undefined);

  return (
    <div className={`issue-item ${issue.severity}`}>
      <Icon name={ICON[issue.severity]} className={`issue-icon ${issue.severity}`} />
      <div className="issue-content">
        <div className="issue-message">{issue.message}</div>
        <div className="row wrap">
          {!compact ? <span className="badge">{issue.rule}</span> : null}
          {!compact
            ? names.map((node) => (
                <button key={node.id} className="link-btn mono" onClick={() => {
                  select([node.id], []);
                  requestFocus(node.id);
                }}>
                  {node.name}
                </button>
              ))
            : null}
          {issue.suggestions.map((suggestion) => (
            <button key={suggestion.title} className="btn btn-sm" title={suggestion.description}
              onClick={() => void applyFix(suggestion.fix)}>
              <Icon name="zap" size={11} /> {suggestion.title}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
