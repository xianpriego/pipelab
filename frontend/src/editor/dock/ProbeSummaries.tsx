import { useMemo } from "react";
import { formatBytes } from "../../lib/format";
import { summarize, type ProbeRow } from "../../lib/probes";

interface ProbeSummariesProps {
  edgeIds: string[];
  rows: ProbeRow[];
  dropped: Record<string, number>;
  linkName: (edgeId: string) => string;
}

/** One line per probed link: rate, average size and key unit spacing. */
export function ProbeSummaries({ edgeIds, rows, dropped, linkName }: ProbeSummariesProps) {
  const summaries = useMemo(() => edgeIds.map((id) => [id, summarize(rows, id)] as const), [edgeIds, rows]);
  if (summaries.length === 0) return null;
  return (
    <div className="probe-summaries">
      {summaries.map(([id, summary]) => (
        <div key={id} className="probe-summary">
          <span className="mono">{linkName(id)}</span>
          <span className="badge">{summary.perSecond ? `${summary.perSecond.toFixed(1)} buf/s` : "— buf/s"}</span>
          <span className="badge">avg {summary.avgSize ? formatBytes(summary.avgSize) : "—"}</span>
          {summary.keyframeInterval ? (
            <span className="badge primary">key every {summary.keyframeInterval.toFixed(2)} s</span>
          ) : null}
          <span className="badge">{summary.events} events</span>
          {dropped[id] ? <span className="badge warning">{dropped[id]} not shown (rate limit)</span> : null}
        </div>
      ))}
    </div>
  );
}
