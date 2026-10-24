import { BaseEdge, EdgeLabelRenderer, getBezierPath, type EdgeProps } from "@xyflow/react";
import { memo, type CSSProperties } from "react";
import { Icon } from "../../components/Icon";
import { formatBitrate, formatFps } from "../../lib/format";
import { prefersReducedMotion } from "../../lib/motion";
import { usePreviewStore } from "../../store/previewStore";
import { useProbeStore } from "../../store/probeStore";
import { useUiStore } from "../../store/uiStore";
import { EdgePackets } from "./EdgePackets";
import { EdgeToolbar } from "./EdgeToolbar";
import type { PipelineFlowEdge } from "./toFlow";

function FlowEdgeView(props: EdgeProps<PipelineFlowEdge>) {
  const { id, data, selected } = props;
  const [path, labelX, labelY] = getBezierPath(props);
  const hovered = useUiStore((state) => state.hoveredEdge === id);
  const animate = useUiStore((state) => state.flowAnimation) && !prefersReducedMotion();
  const tapped = usePreviewStore((state) => state.taps.includes(id));
  const probed = useProbeStore((state) => state.probed.includes(id));
  const running = Boolean(data?.running);
  const discarded = Boolean(data?.discarded);
  const stats = data?.stats;
  const flowing = running && !discarded && Boolean(stats && stats.buffers > 0);
  const classes = [
    "flow-edge",
    data?.severity ? `sev-${data.severity}` : "",
    flowing ? "flowing" : "",
    flowing && !animate ? "dashed-flow" : "",
    discarded ? "discarded" : "",
    probed ? "probed" : "",
    data?.alert ? `runtime-${data.alert}` : "",
    selected ? "selected" : "",
  ];
  const threadOverlay = useUiStore((state) => state.threadOverlay);
  const threadColor = running && threadOverlay ? data?.thread?.color : undefined;
  if (threadColor) classes.push("by-thread");
  const showLabel = running && Boolean(stats) && !discarded;
  const showTools = running && (hovered || Boolean(selected));
  // Labels sit just above the link so the line and its travelling buffers stay visible.
  const labelStyle = { transform: `translate(-50%, -100%) translate(${labelX}px, ${labelY - 5}px)` };
  return (
    <>
      <BaseEdge id={id} path={path} className={classes.join(" ")} interactionWidth={18}
        style={threadColor ? ({ "--thread-color": threadColor } as CSSProperties) : undefined} />
      {flowing && animate && stats ? (
        <EdgePackets path={path} fps={stats.fps} bitrate={stats.bitrate} caps={data?.caps} />
      ) : null}
      <EdgeLabelRenderer>
        {showLabel && stats ? (
          <div className={`edge-label nodrag nopan${probed ? " probed" : ""}`} style={labelStyle}
            title={data?.caps ?? "caps not negotiated yet"}>
            {tapped ? <Icon name="eye" size={10} /> : null}
            {probed ? <Icon name="search" size={10} /> : null}
            {formatFps(stats.fps)} · {formatBitrate(stats.bitrate)}
          </div>
        ) : null}
        {running && discarded ? (
          <div className="edge-label dropped nodrag nopan" style={labelStyle}
            title="The selector drops buffers arriving on this inactive pad">
            dropped
          </div>
        ) : null}
        {showTools ? (
          <div className="edge-toolbar-anchor" style={{ transform: `translate(-50%, 0) translate(${labelX}px, ${labelY + 7}px)` }}>
            <EdgeToolbar edgeId={id} tapped={tapped} probed={probed} />
          </div>
        ) : null}
      </EdgeLabelRenderer>
    </>
  );
}

export const FlowEdge = memo(FlowEdgeView);
