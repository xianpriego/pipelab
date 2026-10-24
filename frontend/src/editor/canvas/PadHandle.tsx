import { Handle, Position } from "@xyflow/react";
import type { MouseEvent, PointerEvent } from "react";
import type { HandleSpec } from "../../lib/pads";

function tooltip(spec: HandleSpec): string {
  const media = spec.mediaTypes.length ? spec.mediaTypes.join("\n") : "unknown caps";
  const kind = spec.kind === "request-new" ? "request a new pad" : spec.presence;
  return `${spec.id} (${kind})\n${media}`;
}

/** Radio of a selector pad (input-selector sink_N, output-selector src_N). */
export interface PadChoice {
  active: boolean;
  /** Requested but deferred by a script (e.g. until the next keyframe). */
  pending?: boolean;
  onSelect: () => void;
}

function stop(event: MouseEvent | PointerEvent) {
  event.stopPropagation();
}

function ChoiceButton({ spec, choice }: { spec: HandleSpec; choice: PadChoice }) {
  return (
    <button
      type="button"
      className={`pad-choice nodrag nopan${choice.active ? " active" : ""}${choice.pending ? " pending" : ""}`}
      role="radio"
      aria-checked={choice.active}
      aria-busy={choice.pending || undefined}
      aria-label={`Make ${spec.id} the active pad`}
      title={choice.active ? `${spec.id} is the active pad`
        : choice.pending ? `Switching to ${spec.id} when the script allows it (e.g. next keyframe)…`
          : `Switch to ${spec.id}`}
      onPointerDown={stop}
      onMouseDown={stop}
      onClick={(event) => {
        event.stopPropagation();
        if (!choice.active && !choice.pending) choice.onSelect();
      }}
    />
  );
}

/** ``port``: inside a component, the port this pad is exposed as (boundary marker). */
export function PadHandle({ spec, choice, port }: { spec: HandleSpec; choice?: PadChoice; port?: string }) {
  const isSink = spec.direction === "sink";
  const marker = port ? (
    <span className="port-marker" title={`Exposed as the component ${isSink ? "input" : "output"} "${port}"`}>
      {isSink ? `${port} ⇥` : `⇥ ${port}`}
    </span>
  ) : null;
  const classes = [
    "pad-row", spec.direction, `pad-${spec.kind}`, choice?.active ? "pad-active" : "", choice && !choice.active ? "pad-inactive" : "",
    port ? "pad-port" : "",
  ];
  return (
    <div className={classes.join(" ")} title={tooltip(spec)}>
      <Handle
        id={spec.id}
        type={isSink ? "target" : "source"}
        position={isSink ? Position.Left : Position.Right}
        className={`pad-handle pad-handle-${spec.kind}`}
      />
      {isSink ? marker : null}
      {choice && isSink ? <ChoiceButton spec={spec} choice={choice} /> : null}
      <span className="pad-label">{spec.label}</span>
      {choice && !isSink ? <ChoiceButton spec={spec} choice={choice} /> : null}
      {isSink ? null : marker}
    </div>
  );
}
