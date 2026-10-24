import { useMemo } from "react";
import type { QueueLevel } from "../../api/events";
import { formatBytes } from "../../lib/format";
import { fillLevel, formatMs, perfInsights, threadLabel, threadNodes, threadsInfo } from "../../lib/perf";
import { useGraphStore } from "../../store/graphStore";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";

function focus(nodeId: string | null) {
  if (!nodeId) return;
  useUiStore.getState().select([nodeId], []);
  useUiStore.getState().requestFocus(nodeId);
}

function QueueRow({ name, queue, onClick }: { name: string; queue: QueueLevel; onClick: () => void }) {
  const limit = (value: number, max: number, format: (v: number) => string) => `${format(value)} / ${max ? format(max) : "∞"}`;
  return (
    <tr className="clickable" onClick={onClick}>
      <td className="mono">{name}</td>
      <td>
        <div className={`queue-meter wide level-${fillLevel(queue)}`}>
          <div className="queue-meter-fill" style={{ width: `${Math.round(queue.fill * 100)}%` }} />
        </div>
      </td>
      <td>{Math.round(queue.fill * 100)}%</td>
      <td>{limit(queue.buffers, queue.max_buffers, String)}</td>
      <td>{limit(queue.time_ms, queue.max_time_ms, (v) => formatMs(v))}</td>
      <td>{limit(queue.bytes, queue.max_bytes, formatBytes)}</td>
      <td className={queue.overruns ? "text-warning" : ""}>{queue.overruns}</td>
      <td>{queue.underruns}</td>
    </tr>
  );
}

/** Where time goes while the pipeline runs: bottlenecks, streaming threads, element latency, queues. */
export function PerfPanel() {
  const graph = useGraphStore((state) => state.graph);
  const stats = useRuntimeStore((state) => state.stats);
  const overlay = useUiStore((state) => state.threadOverlay);
  const name = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;
  const threads = useMemo(() => threadsInfo(stats?.threads), [stats]);
  const insights = useMemo(() => perfInsights(graph, stats?.queues ?? {}, threads), [graph, stats, threads]);

  if (!stats) {
    return (
      <div className="empty-state">
        While the pipeline runs: the streaming threads and their CPU, the time each element takes per buffer and how
        full every queue is — the usual way to find a bottleneck or a missing queue.
      </div>
    );
  }
  const latencies = Object.entries(stats.elements ?? {}).sort(([, a], [, b]) => b.avg_ms - a.avg_ms);
  const queues = Object.entries(stats.queues ?? {});
  return (
    <div className="stats-panel perf-panel">
      {insights.length ? (
        <ul className="perf-insights">
          {insights.map((insight) => (
            <li key={insight.text} className={`badge ${insight.level} clickable`} onClick={() => focus(insight.nodeId)}>
              {insight.text}
            </li>
          ))}
        </ul>
      ) : null}
      <section>
        <div className="row">
          <h4>Streaming threads ({threads.length})</h4>
          <span className="spacer" />
          <label className="row muted">
            <input type="checkbox" checked={overlay} onChange={(e) => useUiStore.getState().setThreadOverlay(e.target.checked)} />
            Colour links by thread
          </label>
        </div>
        <table className="data-table">
          <thead><tr><th /><th>Thread</th><th>CPU</th><th>Runs</th></tr></thead>
          <tbody>
            {threads.map((thread) => (
              <tr key={thread.id} className="clickable" onClick={() => focus(threadNodes(graph, thread)[0] ?? null)}>
                <td><span className="thread-swatch" style={{ background: thread.color }} /></td>
                <td className="mono" title={`Kernel name: ${thread.name} · id ${thread.id}`}>{threadLabel(graph, thread)}</td>
                <td>{thread.cpu === null ? "…" : `${thread.cpu.toFixed(1)}%`}</td>
                <td className="mono muted">{threadNodes(graph, thread).map(name).join(" → ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section>
        <h4>Time per buffer inside each element (last second)</h4>
        {latencies.length ? (
          <table className="data-table">
            <thead><tr><th>Element</th><th>Average</th><th>Max</th><th>Buffers</th></tr></thead>
            <tbody>
              {latencies.map(([id, latency]) => (
                <tr key={id} className="clickable" onClick={() => focus(id)}>
                  <td className="mono">{name(id)}</td>
                  <td>{formatMs(latency.avg_ms)}</td>
                  <td>{formatMs(latency.max_ms)}</td>
                  <td>{latency.samples}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted">No buffer kept its timestamp through an element yet.</p>}
        <p className="faint">
          Measured by matching the timestamp of a buffer entering and leaving the element. Encoders and decoders hold
          several frames on purpose: a high value there is latency, not necessarily a bottleneck. For queues it is the
          waiting time.
        </p>
      </section>
      {queues.length ? (
        <section>
          <h4>Queues</h4>
          <table className="data-table">
            <thead>
              <tr><th>Queue</th><th>Level</th><th /><th>Buffers</th><th>Time</th><th>Bytes</th><th>Overruns</th><th>Underruns</th></tr>
            </thead>
            <tbody>
              {queues.map(([id, queue]) => <QueueRow key={id} name={name(id)} queue={queue} onClick={() => focus(id)} />)}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}
