import { useEffect, useState } from "react";
import type { ElementSummary, GraphNode } from "../../api/types";
import { accentColor } from "../../lib/elementKinds";
import { sanitizeName } from "../../lib/ids";
import { useGraphStore } from "../../store/graphStore";

export function NodeHeader({ node, summary }: { node: GraphNode; summary: ElementSummary | undefined }) {
  const renameNode = useGraphStore((state) => state.renameNode);
  const [name, setName] = useState(node.name);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => setName(node.name), [node.name]);

  const commit = () => {
    const clean = sanitizeName(name);
    if (clean === node.name) return setName(node.name);
    if (!renameNode(node.id, clean)) setError("Name is empty or already used");
    else setError(null);
  };

  return (
    <div className="inspector-section node-header" style={{ borderTopColor: accentColor(summary) }}>
      <label className="field">
        Element name
        <input className={`input mono${error ? " invalid" : ""}`} value={name} aria-label="Element name"
          onChange={(e) => setName(e.target.value)} onBlur={commit} onKeyDown={(e) => e.key === "Enter" && commit()} />
      </label>
      {error ? <div className="prop-error">{error}</div> : null}
      <div className="row">
        <strong className="mono">{node.factory}</strong>
        {summary ? <span className={`family-badge family-${summary.family}`}>{summary.family}</span> : null}
      </div>
      {summary ? (
        <>
          <div>{summary.long_name}</div>
          <div className="muted">{summary.description}</div>
          <div className="row wrap">
            {summary.categories.map((category) => (
              <span key={category} className="badge">{category}</span>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
