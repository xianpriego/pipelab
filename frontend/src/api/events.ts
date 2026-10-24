// Runtime events streamed by the worker through the websocket.

import type { PropertyValue, RuntimeState } from "./types";

export type BusKind =
  | "error" | "warning" | "info" | "eos" | "state-changed" | "qos" | "element" | "tag"
  | "latency" | "stream-start" | "buffering" | "application" | "other";

/** Full RuntimeStatus object. */
export interface StateEvent {
  type: "state";
  state: RuntimeState;
  project_id?: string;
  started_at?: number | null;
  error?: string | null;
}

export interface BusEvent {
  type: "bus";
  kind: BusKind;
  source: string | null;
  node_id: string | null;
  /** Link that failed (caps negotiation errors). */
  edge_id?: string | null;
  path?: string | null;
  text: string;
  debug?: string | null;
  hint?: string | null;
  fields?: Record<string, unknown> | null;
  time?: number | null;
  /** Application messages: structure name. */
  name?: string | null;
}

export interface EdgeStats {
  buffers: number;
  bytes: number;
  fps: number;
  bitrate: number;
  pts?: number | null;
}

/** Time spent inside an element over the last second (same PTS entering and leaving it). */
export interface ElementLatency {
  avg_ms: number;
  max_ms: number;
  samples: number;
}

export interface QueueLevel {
  buffers: number;
  bytes: number;
  time_ms: number;
  max_buffers: number;
  max_bytes: number;
  max_time_ms: number;
  /** Fullest enabled limit, 0..1. */
  fill: number;
  overruns: number;
  underruns: number;
}

/** A streaming thread: kernel name (e.g. "queue0:src"), CPU % (null on the first report), links it pushes. */
export interface ThreadUsage {
  id: number;
  name: string;
  cpu: number | null;
  edges: string[];
}

export interface StatsEvent {
  type: "stats";
  time: number;
  position: number | null;
  duration: number | null;
  edges: Record<string, EdgeStats>;
  elements?: Record<string, ElementLatency>;
  queues?: Record<string, QueueLevel>;
  threads?: ThreadUsage[];
}

export interface CapsEvent {
  type: "caps";
  edge_id: string;
  caps: string;
}

export interface PropertyEvent {
  type: "property";
  node_id: string;
  property: string;
  value: PropertyValue | null;
  ok: boolean;
  error: string | null;
  pad?: string | null;
  /** "runtime" when the element changed the value by itself (e.g. auto-selected pad). */
  origin?: "runtime" | "user";
}

export interface ProbeBuffer {
  kind: "buffer";
  time: number;
  pts: number | null;
  dts: number | null;
  duration: number | null;
  size: number;
  flags: string[];
  offset: number | null;
}

export interface ProbeEventItem {
  kind: "event";
  time: number;
  event: string;
  detail: string;
}

export type ProbeItem = ProbeBuffer | ProbeEventItem;

export interface ProbeEvent {
  type: "probe";
  edge_id: string;
  dropped: number;
  items: ProbeItem[];
}

export interface ReplyEvent {
  type: "reply";
  request_id: string;
  data: unknown;
}

export interface LogEvent {
  type: "log";
  line: string;
}

export type RuntimeEvent =
  | StateEvent | BusEvent | StatsEvent | CapsEvent | PropertyEvent | ReplyEvent | LogEvent | ProbeEvent;

interface FrameHeaderBase {
  type?: "preview";
  /** Sink node id, or `edge:<edge_id>` for link taps. */
  node_id: string;
  edge_id?: string;
}

export interface VideoFrameHeader extends FrameHeaderBase {
  kind: "video";
  mime: string;
  width: number;
  height: number;
}

export interface AudioFrameHeader extends FrameHeaderBase {
  kind: "audio";
  rate: number;
  channels: number;
  format: string;
}

export type FrameHeader = VideoFrameHeader | AudioFrameHeader;

export interface PreviewFrame {
  header: FrameHeader;
  payload: Uint8Array;
}

const EVENT_TYPES = new Set([
  "state", "bus", "stats", "caps", "property", "reply", "log", "probe",
]);

export function parseRuntimeEvent(text: string): RuntimeEvent | null {
  try {
    const value: unknown = JSON.parse(text);
    if (typeof value === "object" && value !== null && EVENT_TYPES.has((value as { type: string }).type)) {
      return value as RuntimeEvent;
    }
  } catch {
    return null;
  }
  return null;
}

export const TAP_PREFIX = "edge:";

export function tapKey(edgeId: string): string {
  return `${TAP_PREFIX}${edgeId}`;
}
