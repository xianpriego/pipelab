// Link probes ("pinchar cables"): batches of buffers/events seen on a link.

import type { ProbeBuffer, ProbeEvent, ProbeItem, ProbeLogEvent, ScriptEvent, ScriptLevel } from "../api/events";

export const PROBE_ROW_LIMIT = 2000;

/** A message logged by a probe script. */
export interface ProbeLogItem {
  kind: "log";
  time: number | null;
  level: ScriptLevel;
  message: string;
  scriptName: string;
  fields?: Record<string, unknown> | null;
}

export type ProbeRowItem = ProbeItem | ProbeLogItem;

export interface ProbeRow {
  seq: number;
  /** Probed link, or "" for script messages. */
  edgeId: string;
  /** Script that logged the row. */
  scriptId?: string;
  /** Probe rule set that logged the row ("<instance>/<probe id>" inside components). */
  probeId?: string;
  item: ProbeRowItem;
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

/** Script messages share the probe table (same pause and row cap). */
export function ingestScript(data: ProbeData, event: ScriptEvent, paused: boolean, limit = PROBE_ROW_LIMIT): ProbeData {
  if (paused) return { ...data, skipped: data.skipped + 1 };
  const item: ProbeLogItem = {
    kind: "log", time: event.time ?? null, level: event.level, message: event.message,
    scriptName: event.name, fields: event.fields,
  };
  return appendRows(data, [{ edgeId: "", scriptId: event.script_id, item }], limit);
}

/** ``log`` actions of probe rule sets share the table too. */
export function ingestProbeLog(
  data: ProbeData, event: ProbeLogEvent, probeName: string, paused: boolean, limit = PROBE_ROW_LIMIT,
): ProbeData {
  if (paused) return { ...data, skipped: data.skipped + 1 };
  const item: ProbeLogItem = {
    kind: "log", time: event.time ?? null, level: event.level, message: event.message, scriptName: probeName,
  };
  return appendRows(data, [{ edgeId: "", probeId: event.probe, item }], limit);
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
    .map((row) => row.item)
    .filter((item): item is ProbeItem => item.kind !== "log");
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
