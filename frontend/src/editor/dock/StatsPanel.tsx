import { formatBitrate, formatBytes, formatClock, formatFps, truncate } from "../../lib/format";
import { useGraphStore } from "../../store/graphStore";
import { useRuntimeStore } from "../../store/runtimeStore";

export function StatsPanel() {
  const graph = useGraphStore((state) => state.graph);
  const stats = useRuntimeStore((state) => state.stats);
  const caps = useRuntimeStore((state) => state.caps);
  const name = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;

  if (!stats) return <div className="empty-state">Statistics appear here while the pipeline runs.</div>;
  return (
    <div className="stats-panel">
      <div className="row muted">
        <span>Position {formatClock(stats.position)}</span>
        {stats.duration ? <span>/ {formatClock(stats.duration)}</span> : null}
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>Link</th><th>Caps</th><th>Buffers</th><th>Rate</th><th>Bitrate</th><th>Bytes</th>
          </tr>
        </thead>
        <tbody>
          {graph.edges.map((edge) => {
            const row = stats.edges[edge.id];
            return (
              <tr key={edge.id}>
                <td className="mono">{name(edge.source)}.{edge.source_pad} → {name(edge.target)}.{edge.target_pad}</td>
                <td className="mono" title={caps[edge.id]}>{caps[edge.id] ? truncate(caps[edge.id], 70) : "—"}</td>
                <td>{row?.buffers ?? 0}</td>
                <td>{row ? formatFps(row.fps) : "—"}</td>
                <td>{row ? formatBitrate(row.bitrate) : "—"}</td>
                <td>{row ? formatBytes(row.bytes) : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
