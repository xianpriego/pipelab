import { useMemo } from "react";
import { Icon } from "../../components/Icon";
import { hasTrigger, scriptsFor } from "../../lib/scripts";
import { useGraphStore } from "../../store/graphStore";
import { useUiStore } from "../../store/uiStore";
import { setLinkProbe, setLinkTap } from "../actions";
import { triggerScript } from "../scriptActions";
import { ADVANCED } from "../../lib/features";

interface EdgeToolbarProps {
  edgeId: string;
  tapped: boolean;
  probed: boolean;
}

/** Floating actions of a link: watch what flows through it, probe its buffers and events. */
export function EdgeToolbar({ edgeId, tapped, probed }: EdgeToolbarProps) {
  const hoverEdge = useUiStore((state) => state.hoverEdge);
  const graph = useGraphStore((state) => state.graph);
  const triggers = useMemo(
    () => scriptsFor(graph, "edge", edgeId).filter((script) => script.enabled && hasTrigger(script.code)),
    [graph, edgeId],
  );
  return (
    <div
      className="edge-toolbar nodrag nopan"
      onMouseEnter={() => hoverEdge(edgeId)}
      onMouseLeave={() => hoverEdge(null)}
    >
      <button type="button" className={`edge-tool${tapped ? " on" : ""}`} aria-pressed={tapped}
        title="Preview what flows through this link" onClick={() => void setLinkTap(edgeId, !tapped)}>
        <Icon name="eye" size={12} /> Watch
      </button>
      <button type="button" className={`edge-tool${probed ? " on" : ""}`} aria-pressed={probed}
        title="Inspect the buffers and events crossing this link" onClick={() => void setLinkProbe(edgeId, !probed)}>
        <Icon name="search" size={12} /> Probe
      </button>
      {ADVANCED && triggers.map((script) => (
        <button key={script.id} type="button" className="edge-tool" title={`Call on_trigger of "${script.name}"`}
          onClick={() => void triggerScript(script, null)}>
          <Icon name="zap" size={12} /> {script.name}
        </button>
      ))}
    </div>
  );
}
