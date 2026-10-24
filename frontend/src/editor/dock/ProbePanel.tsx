import { useMemo, useState } from "react";
import { formatBytes, formatSeconds } from "../../lib/format";
import { isKeyframe, type ProbeRow, type ProbeRowItem } from "../../lib/probes";
import { scriptsOf, targetLabel } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useProbeStore } from "../../store/probeStore";
import { ProbeSummaries } from "./ProbeSummaries";
import { useAutoScroll } from "./useAutoScroll";
import { ADVANCED } from "../../lib/features";

const VISIBLE = 500;
type KindFilter = "all" | "buffer" | "event" | "log";

function rowClass(item: ProbeRowItem): string {
  if (item.kind === "event") return "probe-row event";
  if (item.kind === "log") return `probe-row log level-${item.level}`;
  return `probe-row buffer${isKeyframe(item) ? " key" : ""}`;
}

function Cells({ item }: { item: ProbeRowItem }) {
  if (item.kind === "log") {
    return (
      <>
        <td colSpan={4} />
        <td><span className={`badge ${item.level === "info" ? "primary" : item.level}`}>{item.scriptName}</span></td>
        <td className="probe-detail" title={item.message}>{item.message}</td>
      </>
    );
  }
  if (item.kind === "event") {
    return (
      <>
        <td colSpan={4} />
        <td><span className="badge primary">{item.event}</span></td>
        <td className="probe-detail" title={item.detail}>{item.detail}</td>
      </>
    );
  }
  return (
    <>
      <td>{formatSeconds(item.pts)}</td>
      <td>{formatSeconds(item.dts)}</td>
      <td>{formatSeconds(item.duration)}</td>
      <td>{formatBytes(item.size)}</td>
      <td>
        {isKeyframe(item) ? <span className="badge success" title="Key unit (no delta-unit flag)">K</span> : null}{" "}
        {item.flags.join(" ")}
      </td>
      <td>{item.offset ?? ""}</td>
    </>
  );
}

export function ProbePanel() {
  const { rows, dropped, skipped, probed, paused, setPaused, clear } = useProbeStore();
  const graph = useGraphStore((state) => state.graph);
  const { edges, nodes } = graph;
  const [link, setLink] = useState("all");
  const [kind, setKind] = useState<KindFilter>("all");

  const linkName = (edgeId: string) => {
    const edge = edges.find((e) => e.id === edgeId);
    if (!edge) return edgeId;
    const name = (id: string) => nodes.find((n) => n.id === id)?.name ?? id;
    return `${name(edge.source)}.${edge.source_pad} → ${name(edge.target)}.${edge.target_pad}`;
  };
  const sourceName = (row: ProbeRow) => {
    if (row.probeId) return `◉ ${row.item.kind === "log" ? row.item.scriptName : row.probeId}`;
    if (!row.scriptId) return linkName(row.edgeId);
    const script = scriptsOf(graph).find((s) => s.id === row.scriptId);
    return script ? targetLabel(graph, script.target) : "script";
  };
  const links = useMemo(
    () => [...new Set([...probed, ...rows.map((row) => row.edgeId)])].filter(Boolean),
    [probed, rows],
  );
  const hasScripts = rows.some((row) => row.scriptId || row.probeId);
  const visible = useMemo(
    () => rows
      .filter((row: ProbeRow) => (link === "all" || row.edgeId === link || (link === "scripts" && (row.scriptId || row.probeId)))
        && (kind === "all" || row.item.kind === kind))
      .slice(-VISIBLE),
    [rows, link, kind],
  );
  const scroller = useAutoScroll<HTMLDivElement>(visible.length, !paused);

  if (links.length === 0 && !hasScripts) {
    return (
      <div className="empty-state">
        Probe a link while the pipeline runs (hover it and press <strong>Probe</strong>) to list every buffer and
        event that crosses it: timestamps, sizes, key units, caps, segments, EOS…
        {ADVANCED ? <> Messages logged by probe scripts (<code>ctx.log</code>) and the <strong>log</strong> actions of
          no-code probes also appear here.</> : null}
      </div>
    );
  }
  return (
    <div className="panel-with-toolbar">
      <div className="panel-toolbar">
        <select className="select" value={link} onChange={(e) => setLink(e.target.value)} aria-label="Probed link">
          <option value="all">All probed links</option>
          {hasScripts ? <option value="scripts">Scripts &amp; probes</option> : null}
          {links.map((id) => <option key={id} value={id}>{linkName(id)}</option>)}
        </select>
        <select className="select" value={kind} onChange={(e) => setKind(e.target.value as KindFilter)} aria-label="Item kind">
          <option value="all">Buffers & events</option>
          <option value="buffer">Buffers</option>
          <option value="event">Events</option>
          {ADVANCED ? <option value="log">Script &amp; probe logs</option> : null}
        </select>
        <button className="btn btn-sm" onClick={() => setPaused(!paused)}>{paused ? "Resume" : "Pause"}</button>
        <button className="btn btn-sm" onClick={clear}>Clear</button>
        <span className="muted nowrap">
          {visible.length} / {rows.length} rows{paused && skipped ? ` · ${skipped} skipped while paused` : ""}
        </span>
      </div>
      <ProbeSummaries edgeIds={link === "all" ? links : link === "scripts" ? [] : [link]} rows={rows} dropped={dropped}
        linkName={linkName} />
      <div className="probe-table-wrap" ref={scroller}>
        <table className="data-table probe-table">
          <thead>
            <tr>
              <th>Time</th><th>Link</th><th>Kind</th><th>PTS</th><th>DTS</th><th>Duration</th><th>Size</th>
              <th>Flags / event</th><th>Detail</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.seq} className={rowClass(row.item)}>
                <td>{row.item.time === null ? "" : formatSeconds(row.item.time)}</td>
                <td className="mono probe-link">{sourceName(row)}</td>
                <td>{row.item.kind}</td>
                <Cells item={row.item} />
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
