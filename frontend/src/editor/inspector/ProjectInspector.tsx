import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";

const SHORTCUTS: [string, string][] = [
  ["Drag from palette", "add element"],
  ["Drag pad → pad", "link (checked)"],
  ["Del / Backspace", "delete selection"],
  ["Ctrl+Z / Ctrl+Shift+Z", "undo / redo"],
  ["Ctrl+C / Ctrl+V", "copy / paste"],
  ["Ctrl+S", "save now"],
  ["Shift+drag", "box selection"],
];

export function ProjectInspector() {
  const meta = useProjectStore((state) => state.meta);
  const setDescription = useProjectStore((state) => state.setDescription);
  const nodeCount = useGraphStore((state) => state.graph.nodes.length);
  const edgeCount = useGraphStore((state) => state.graph.edges.length);
  if (!meta) return null;
  return (
    <div className="inspector-scroll">
      <div className="inspector-section">
        <h3>Pipeline</h3>
        <label className="field">
          Description
          <textarea className="textarea" rows={4} value={meta.description} placeholder="What is this pipeline for?"
            onChange={(event) => setDescription(event.target.value)} style={{ fontFamily: "var(--font)" }} />
        </label>
        <div className="muted">{nodeCount} elements · {edgeCount} links</div>
      </div>
      <div className="inspector-section">
        <h3>Tips</h3>
        <dl className="shortcut-list">
          {SHORTCUTS.map(([keys, action]) => (
            <div key={keys}>
              <dt>{keys}</dt>
              <dd>{action}</dd>
            </div>
          ))}
        </dl>
        <p className="faint">Select an element to edit its properties; select a link to see its caps and insert
          elements on it.</p>
      </div>
    </div>
  );
}
