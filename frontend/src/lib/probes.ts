// Link probes ("pinchar cables"): batches of buffers/events seen on a link.

import type { ProbeBuffer, ProbeEvent, ProbeItem } from "../api/events";

export const PROBE_ROW_LIMIT = 2000;

export interface ProbeRow {
  seq: number;
  /** Probed link. */
  edgeId: string;
  item: ProbeItem;
}

export interface ProbeData {
  rows: ProbeRow[];
  seq: number;
  /** Items the worker could not send (rate limit), per link. */
  dropped: Record<string, number>;
  /** Items ignored while the view was paused. */
  skipped: number;
}

export function emptyProbeData(): ProbeData {
  return { rows: [], seq: 0, dropped: {}, skipped: 0 };
}

function appendRows(data: ProbeData, added: Omit<ProbeRow, "seq">[], limit: number): ProbeData {
  let seq = data.seq;
  const rows = [...data.rows, ...added.map((row) => ({ ...row, seq: ++seq }))];
  return { ...data, seq, rows: rows.length > limit ? rows.slice(rows.length - limit) : rows };
}

export function ingestProbe(data: ProbeData, event: ProbeEvent, paused: boolean, limit = PROBE_ROW_LIMIT): ProbeData {
  const dropped = event.dropped
    ? { ...data.dropped, [event.edge_id]: (data.dropped[event.edge_id] ?? 0) + event.dropped }
    : data.dropped;
  if (paused) return { ...data, dropped, skipped: data.skipped + event.items.length };
  return appendRows({ ...data, dropped }, event.items.map((item) => ({ edgeId: event.edge_id, item })), limit);
}

export function isKeyframe(buffer: ProbeBuffer): boolean {
  return !buffer.flags.includes("delta-unit");
}

export interface ProbeSummary {
  buffers: number;
  events: number;
  perSecond: number | null;
  avgSize: number | null;
  /** Seconds between key units, when the stream has delta units at all. */
  keyframeInterval: number | null;
}

const WINDOW = 200;

function averageGap(times: number[]): number | null {
  if (times.length < 2) return null;
  return (times[times.length - 1] - times[0]) / (times.length - 1);
}

export function summarize(rows: ProbeRow[], edgeId: string): ProbeSummary {
  const items = rows
    .filter((row) => row.edgeId === edgeId)
    .map((row) => row.item);
  const buffers = items.filter((item): item is ProbeBuffer => item.kind === "buffer");
  const recent = buffers.slice(-WINDOW);
  const gap = averageGap(recent.map((buffer) => buffer.time));
  const hasDeltas = buffers.some((buffer) => !isKeyframe(buffer));
  const keyTimes = buffers.filter(isKeyframe).map((buffer) => buffer.pts ?? buffer.time);
  return {
    buffers: buffers.length,
    events: items.length - buffers.length,
    perSecond: gap ? 1 / gap : null,
    avgSize: recent.length ? recent.reduce((sum, buffer) => sum + buffer.size, 0) / recent.length : null,
    keyframeInterval: hasDeltas ? averageGap(keyTimes) : null,
  };
}
