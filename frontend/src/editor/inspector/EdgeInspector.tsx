import type { ElementInfo, GraphEdge } from "../../api/types";
import { useElementDetails } from "../../hooks/useElementDetails";
import { formatBitrate, formatBytes, formatFps } from "../../lib/format";
import { findTemplate } from "../../lib/pads";
import { useGraphStore } from "../../store/graphStore";
import { usePreviewStore } from "../../store/previewStore";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { useUiStore } from "../../store/uiStore";
import { useValidationStore } from "../../store/validationStore";
import { IssueItem } from "../dock/IssueItem";
import { setLinkProbe, setLinkTap } from "../actions";
import { useProbeStore } from "../../store/probeStore";
import { ScriptsSection } from "../scripts/ScriptsSection";
import { InsertOnEdge } from "./InsertOnEdge";
import { ADVANCED } from "../../lib/features";

function templateCaps(details: ElementInfo | undefined, pad: string): string {
  if (!details) return "…";
  return findTemplate(details.pad_templates, pad)?.caps ?? "unknown pad";
}

export function EdgeInspector({ edgeId }: { edgeId: string }) {
  const edge = useGraphStore((state) => state.graph.edges.find((e) => e.id === edgeId));
  const nodes = useGraphStore((state) => state.graph.nodes);
  const caps = useRuntimeStore((state) => state.caps[edgeId]);
  const stats = useRuntimeStore((state) => state.stats?.edges[edgeId]);
  const issues = useValidationStore((state) => state.issues);
  const source = nodes.find((n) => n.id === edge?.source);
  const target = nodes.find((n) => n.id === edge?.target);
  const sourceDetails = useElementDetails(source?.factory);
  const targetDetails = useElementDetails(target?.factory);

  if (!edge || !source || !target) return null;
  const edgeIssues = issues.filter((issue) => issue.edge_ids.includes(edge.id));

  return (
    <div className="inspector-scroll">
      <div className="inspector-section">
        <h3>Link</h3>
        <div className="mono link-title">
          {source.name}.{edge.source_pad} → {target.name}.{edge.target_pad}
        </div>
        <EdgeActions edge={edge} />
      </div>
      {edgeIssues.length ? (
        <div className="inspector-section">
          <h3>Issues</h3>
          {edgeIssues.map((issue) => <IssueItem key={issue.id} issue={issue} compact />)}
        </div>
      ) : null}
      <WatchLink edgeId={edge.id} />
      <ProbeLink edgeId={edge.id} />
      {ADVANCED ? <ScriptsSection target={{ kind: "edge", id: edge.id }} /> : null}
      <div className="inspector-section">
        <h3>Insert element on this link</h3>
        <InsertOnEdge edgeId={edge.id} />
      </div>
      <div className="inspector-section">
        <h3>Negotiated caps</h3>
        {caps ? <pre className="caps-block">{caps.replace(/, /g, ",\n  ")}</pre> : (
          <div className="muted">Run the pipeline to see the caps negotiated on this link.</div>
        )}
        {stats ? (
          <div className="row wrap">
            <span className="badge">{formatFps(stats.fps)}</span>
            <span className="badge">{formatBitrate(stats.bitrate)}</span>
            <span className="badge">{stats.buffers} buffers</span>
            <span className="badge">{formatBytes(stats.bytes)}</span>
          </div>
        ) : null}
      </div>
      <div className="inspector-section">
        <h3>Template caps</h3>
        <div className="muted">{source.name}.{edge.source_pad}</div>
        <pre className="caps-block">{templateCaps(sourceDetails, edge.source_pad)}</pre>
        <div className="muted">{target.name}.{edge.target_pad}</div>
        <pre className="caps-block">{templateCaps(targetDetails, edge.target_pad)}</pre>
      </div>
    </div>
  );
}

function WatchLink({ edgeId }: { edgeId: string }) {
  const running = useRuntimeStore((state) => isActive(state.state));
  const tapped = usePreviewStore((state) => state.taps.includes(edgeId));
  return (
    <div className="inspector-section row">
      <span className="spacer">
        <strong>Watch this link</strong>
        <div className="muted">
          {running ? "Preview what flows here: video is decoded to frames, audio to a meter." : "Available while running."}
        </div>
      </span>
      <label className="switch" title="Preview the data flowing through this link">
        <input type="checkbox" checked={tapped} disabled={!running} aria-label="Watch this link"
          onChange={(event) => void setLinkTap(edgeId, event.target.checked)} />
        <span />
      </label>
    </div>
  );
}

function EdgeActions({ edge }: { edge: GraphEdge }) {
  const removeElements = useGraphStore((state) => state.removeElements);
  const select = useUiStore((state) => state.select);
  return (
    <div className="row">
      <button className="btn btn-sm" onClick={() => select([edge.source], [])}>Select source</button>
      <button className="btn btn-sm" onClick={() => select([edge.target], [])}>Select target</button>
      <span className="spacer" />
      <button className="btn btn-sm btn-danger" onClick={() => {
        removeElements([], [edge.id]);
        select([], []);
      }}>
        Unlink
      </button>
    </div>
  );
}

function ProbeLink({ edgeId }: { edgeId: string }) {
  const running = useRuntimeStore((state) => isActive(state.state));
  const probed = useProbeStore((state) => state.probed.includes(edgeId));
  return (
    <div className="inspector-section row">
      <span className="spacer">
        <strong>Probe this link</strong>
        <div className="muted">
          {running ? "List every buffer (pts, size, flags) and event crossing it in the Probe tab." : "Available while running."}
        </div>
      </span>
      <label className="switch" title="Inspect buffers and events on this link">
        <input type="checkbox" checked={probed} disabled={!running} aria-label="Probe this link"
          onChange={(event) => void setLinkProbe(edgeId, event.target.checked)} />
        <span />
      </label>
    </div>
  );
}
