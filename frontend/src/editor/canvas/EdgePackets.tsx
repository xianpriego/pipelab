import { memo } from "react";
import { PACKET_TRAVEL_SECONDS, mediaClass, packetPlan } from "../../lib/packets";

interface EdgePacketsProps {
  path: string;
  fps: number;
  bitrate: number;
  caps: string | undefined;
}

/** Dots travelling along a link: density follows the buffer rate, size the bitrate. */
function EdgePacketsView({ path, fps, bitrate, caps }: EdgePacketsProps) {
  const plan = packetPlan(fps, bitrate);
  if (plan.count === 0) return null;
  return (
    <g className={`packets media-${mediaClass(caps)}`} pointerEvents="none">
      {Array.from({ length: plan.count }, (_, index) => (
        <circle key={index} r={plan.radius} className="packet">
          <animateMotion
            dur={`${PACKET_TRAVEL_SECONDS}s`}
            repeatCount="indefinite"
            begin={`${(-index * PACKET_TRAVEL_SECONDS) / plan.count}s`}
            path={path}
          />
        </circle>
      ))}
    </g>
  );
}

export const EdgePackets = memo(EdgePacketsView);
