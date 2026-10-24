import { getBezierPath, type ConnectionLineComponentProps } from "@xyflow/react";
import { compatHint } from "../../lib/compat";
import type { HandleSpec } from "../../lib/pads";
import type { ElementFlowNode } from "./toFlow";

function mediaOf(node: Pick<ElementFlowNode, "data"> | null | undefined, handleId: string | null | undefined): string[] {
  if (!node || !handleId) return [];
  const specs: HandleSpec[] = [...node.data.handles.sinks, ...node.data.handles.srcs];
  return specs.find((spec) => spec.id === handleId)?.mediaTypes ?? [];
}

export function ConnectionLine(props: ConnectionLineComponentProps<ElementFlowNode>) {
  const { fromX, fromY, toX, toY, fromPosition, toPosition, fromNode, fromHandle, toNode, toHandle } = props;
  const [path] = getBezierPath({
    sourceX: fromX, sourceY: fromY, sourcePosition: fromPosition, targetX: toX, targetY: toY, targetPosition: toPosition,
  });
  let status = "pending";
  if (props.connectionStatus === "invalid") status = "invalid";
  else if (toNode && toHandle) {
    const from = mediaOf(fromNode, fromHandle.id);
    const to = mediaOf(toNode, toHandle.id);
    status = fromHandle.type === "source" ? compatHint(from, to) : compatHint(to, from);
  }
  return (
    <g className={`connection-line ${status}`}>
      <path d={path} fill="none" />
      <circle cx={toX} cy={toY} r={4} />
    </g>
  );
}
