import type { NodePerf } from "../../lib/perf";
import { fillLevel, formatMs } from "../../lib/perf";

/** While running: time spent inside the element and, for queues, how full they are. */
export function NodePerfBar({ perf }: { perf: NodePerf }) {
  const { latency, queue } = perf;
  return (
    <div className="node-perf">
      {queue ? (
        <div className={`queue-meter level-${fillLevel(queue)}`}
          title={`Queue level: ${queue.buffers}/${queue.max_buffers || "∞"} buffers, ` +
            `${queue.time_ms}/${queue.max_time_ms || "∞"} ms, ${queue.bytes}/${queue.max_bytes || "∞"} bytes · ` +
            `${queue.overruns} overruns, ${queue.underruns} underruns`}>
          <div className="queue-meter-fill" style={{ width: `${Math.round(queue.fill * 100)}%` }} />
        </div>
      ) : null}
      <div className="node-perf-text mono">
        {latency ? (
          <span title={`Time inside the element over the last second: average ${formatMs(latency.avg_ms)}, ` +
            `max ${formatMs(latency.max_ms)} (${latency.samples} buffers)`}>⏱ {formatMs(latency.avg_ms)}</span>
        ) : null}
        {queue ? <span>{Math.round(queue.fill * 100)}%</span> : null}
        {queue?.overruns ? <span className="node-perf-alert" title="Times the queue was full">▲{queue.overruns}</span> : null}
      </div>
    </div>
  );
}
