import { useMemo, useState } from "react";
import type { BusKind } from "../../api/events";
import { useGraphStore } from "../../store/graphStore";
import type { BusEntry } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";
import { useAutoScroll } from "./useAutoScroll";

const VISIBLE = 500;
type Filter = "all" | "problems" | BusKind;
const FILTERS: [Filter, string][] = [
  ["all", "All"], ["problems", "Errors & warnings"], ["application", "Application (probes)"], ["state-changed", "State"],
  ["eos", "EOS"],
  ["element", "Element"], ["tag", "Tags"], ["qos", "QoS"], ["info", "Info"],
];

function matches(entry: BusEntry, filter: Filter, text: string): boolean {
  if (filter === "problems" && entry.kind !== "error" && entry.kind !== "warning") return false;
  if (filter !== "all" && filter !== "problems" && entry.kind !== filter) return false;
  if (!text) return true;
  const fields = entry.kind === "application" && entry.fields ? JSON.stringify(entry.fields) : "";
  const haystack = `${entry.source ?? ""} ${entry.name ?? ""} ${entry.text} ${entry.debug ?? ""} ${fields}`.toLowerCase();
  return haystack.includes(text);
}

/** ``post-message`` fields shown inline as ``key=value`` chips. */
function FieldChips({ fields }: { fields: Record<string, unknown> }) {
  return (
    <span className="bus-fields">
      {Object.entries(fields).map(([key, value]) => (
        <span key={key} className="field-chip mono">{key}={typeof value === "string" ? value : JSON.stringify(value)}</span>
      ))}
    </span>
  );
}

function nodeName(nodes: { id: string; name: string }[], id: string): string {
  return nodes.find((node) => node.id === id)?.name ?? id;
}

function time(entry: BusEntry): string {
  if (typeof entry.time === "number") return entry.time.toFixed(3);
  return new Date(entry.receivedAt).toLocaleTimeString();
}

export function BusPanel() {
  const bus = useRuntimeStore((state) => state.bus);
  const nodes = useGraphStore((state) => state.graph.nodes);
  const edges = useGraphStore((state) => state.graph.edges);
  const select = useUiStore((state) => state.select);
  const requestFocus = useUiStore((state) => state.requestFocus);
  const [filter, setFilter] = useState<Filter>("all");
  const [text, setText] = useState("");
  const [expanded, setExpanded] = useState<number | null>(null);
  const visible = useMemo(() => {
    const q = text.trim().toLowerCase();
    return bus.filter((entry) => matches(entry, filter, q)).slice(-VISIBLE);
  }, [bus, filter, text]);
  const scroller = useAutoScroll<HTMLDivElement>(visible.length, expanded === null);

  return (
    <div className="panel-with-toolbar">
      <div className="panel-toolbar">
        <select className="select" value={filter} onChange={(e) => setFilter(e.target.value as Filter)} aria-label="Message kind">
          {FILTERS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </select>
        <input className="input" placeholder="Filter messages…" value={text} onChange={(e) => setText(e.target.value)} />
        <span className="muted nowrap">{visible.length} / {bus.length}</span>
      </div>
      <div className="bus-list" ref={scroller}>
        {visible.length === 0 ? <div className="empty-state">No bus messages yet. Run the pipeline to see them.</div> : null}
        {visible.map((entry) => {
          const node = nodes.find((n) => n.id === entry.node_id);
          const edge = entry.edge_id ? edges.find((e) => e.id === entry.edge_id) : undefined;
          const open = expanded === entry.seq;
          return (
            <div key={entry.seq} className={`bus-row kind-${entry.kind}`}>
              <div className="bus-line" onClick={() => setExpanded(open ? null : entry.seq)}>
                <span className="mono faint">{time(entry)}</span>
                <span className={`badge kind ${entry.kind}`}>{entry.kind}</span>
                {node || entry.source ? (
                  <button className="link-btn mono" onClick={(event) => {
                    event.stopPropagation();
                    if (node) {
                      select([node.id], []);
                      requestFocus(node.id);
                    }
                  }}>
                    {node?.name ?? entry.source}
                  </button>
                ) : null}
                {edge ? (
                  <button className="link-btn mono bus-link" title="Select the link that failed" onClick={(event) => {
                    event.stopPropagation();
                    select([], [edge.id]);
                    requestFocus(edge.target);
                  }}>
                    {nodeName(nodes, edge.source)}.{edge.source_pad} → {nodeName(nodes, edge.target)}.{edge.target_pad}
                  </button>
                ) : null}
                {entry.kind === "application" && entry.name ? <strong className="mono app-name">{entry.name}</strong> : null}
                {entry.kind !== "application" || entry.text !== entry.name ? <span className="bus-text">{entry.text}</span> : null}
                {entry.kind === "application" && entry.fields ? <FieldChips fields={entry.fields} /> : null}
              </div>
              {open ? (
                <div className="bus-details">
                  {entry.hint ? <div className="bus-hint">💡 {entry.hint}</div> : null}
                  {entry.path ? <div className="mono faint">{entry.path}</div> : null}
                  {entry.debug ? <pre>{entry.debug}</pre> : null}
                  {entry.fields ? <pre>{JSON.stringify(entry.fields, null, 2)}</pre> : null}
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </div>
  );
}
