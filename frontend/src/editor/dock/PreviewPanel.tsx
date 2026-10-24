import { tapKey } from "../../api/events";
import type { Graph } from "../../api/types";
import { previewKind } from "../../lib/elementKinds";
import { useCatalogStore } from "../../store/catalogStore";
import { useGraphStore } from "../../store/graphStore";
import { usePreviewStore } from "../../store/previewStore";
import { isActive } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { setLinkTap } from "../actions";
import { AudioTile } from "./AudioTile";
import { VideoTile } from "./VideoTile";

function linkLabel(graph: Graph, edgeId: string): string {
  const edge = graph.edges.find((e) => e.id === edgeId);
  if (!edge) return `link ${edgeId}`;
  const name = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;
  return `link ${name(edge.source)}.${edge.source_pad} → ${name(edge.target)}.${edge.target_pad}`;
}

export function PreviewPanel() {
  const graph = useGraphStore((state) => state.graph);
  const byName = useCatalogStore((state) => state.byName);
  const running = useRuntimeStore((state) => isActive(state.state));
  const taps = usePreviewStore((state) => state.taps);
  // A primitive selector: re-render when a tap's kind changes, not on every frame.
  const tapKinds = usePreviewStore((state) =>
    state.taps.map((id) => state.previews[tapKey(id)]?.kind ?? "video").join(","),
  ).split(",");
  const sinks = graph.nodes
    .filter((node) => node.preview !== "off")
    .map((node) => ({ node, kind: previewKind(byName[node.factory]) }))
    .filter((entry) => entry.kind !== null);

  if (sinks.length === 0 && taps.length === 0) {
    return (
      <div className="empty-state">
        <h3>Nothing to preview</h3>
        <p>Add a display or audio sink (autovideosink, glimagesink, autoaudiosink…), or select a link while running
          and enable "Watch this link". File outputs appear in the Outputs tab.</p>
      </div>
    );
  }
  return (
    <div className="preview-grid">
      {sinks.map(({ node, kind }) =>
        kind === "video" ? (
          <VideoTile key={node.id} previewKey={node.id} name={node.name} running={running} />
        ) : (
          <AudioTile key={node.id} previewKey={node.id} name={node.name} running={running} />
        ),
      )}
      {taps.map((edgeId, index) => {
        const key = tapKey(edgeId);
        const close = () => void setLinkTap(edgeId, false);
        const label = linkLabel(graph, edgeId);
        return tapKinds[index] === "audio" ? (
          <AudioTile key={key} previewKey={key} name={label} running={running} onClose={close} />
        ) : (
          <VideoTile key={key} previewKey={key} name={label} running={running} onClose={close} />
        );
      })}
    </div>
  );
}
