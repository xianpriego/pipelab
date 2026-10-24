// Pure reducer turning runtime events into UI state.

import type { SlotInstance } from "../api/dynamic";
import type { BusEvent, PropertyEvent, RuntimeEvent, StatsEvent } from "../api/events";
import type { PropertyValue, RuntimeState } from "../api/types";

export const BUS_LIMIT = 2000;
export const LOG_LIMIT = 5000;

export interface BusEntry extends BusEvent {
  seq: number;
  receivedAt: number;
}

export interface LogEntry {
  seq: number;
  line: string;
}

export type NodeAlert = "error" | "warning";

/** Values in effect inside the running elements: node id → property (or `pad::property`) → value. */
export type LiveProps = Record<string, Record<string, PropertyValue>>;

export interface RuntimeData {
  state: RuntimeState;
  error: string | null;
  bus: BusEntry[];
  logs: LogEntry[];
  stats: StatsEvent | null;
  caps: Record<string, string>;
  nodeAlerts: Record<string, NodeAlert>;
  /** Links reported by bus errors/warnings (e.g. failed caps negotiation). */
  edgeAlerts: Record<string, NodeAlert>;
  lastProperty: PropertyEvent | null;
  liveProps: LiveProps;
  /** Values requested from the UI that a script deferred (e.g. switch at the next keyframe). */
  pending: LiveProps;
  /** Live instances per slot id (from ``instances`` events and GET /runtime/instances). */
  instances: Record<string, SlotInstance[]>;
  eos: boolean;
  seq: number;
}

export function initialRuntime(): RuntimeData {
  return {
    state: "idle", error: null, bus: [], logs: [], stats: null, caps: {}, nodeAlerts: {}, edgeAlerts: {},
    lastProperty: null, liveProps: {}, pending: {}, instances: {}, eos: false, seq: 0,
  };
}

function capped<T>(items: T[], item: T, limit: number): T[] {
  const next = items.length >= limit ? items.slice(items.length - limit + 1) : items.slice();
  next.push(item);
  return next;
}

function withAlert(alerts: Record<string, NodeAlert>, id: string | null | undefined, kind: BusEvent["kind"]) {
  if (!id || (kind !== "error" && kind !== "warning") || alerts[id] === "error") return alerts;
  return { ...alerts, [id]: kind };
}

function applyBus(state: RuntimeData, event: BusEvent, now: number): RuntimeData {
  const seq = state.seq + 1;
  return {
    ...state,
    seq,
    nodeAlerts: withAlert(state.nodeAlerts, event.node_id, event.kind),
    edgeAlerts: withAlert(state.edgeAlerts, event.edge_id, event.kind),
    eos: state.eos || event.kind === "eos",
    error: event.kind === "error" ? event.text : state.error,
    bus: capped(state.bus, { ...event, seq, receivedAt: now }, BUS_LIMIT),
  };
}

export function applyRuntimeEvent(state: RuntimeData, event: RuntimeEvent, now = Date.now()): RuntimeData {
  switch (event.type) {
    case "state":
      if (event.state === "starting") {
        return { ...initialRuntime(), state: "starting", seq: state.seq };
      }
      return { ...state, state: event.state, error: event.error ?? state.error };
    case "bus":
      return applyBus(state, event, now);
    case "stats":
      return { ...state, stats: event };
    case "caps":
      return { ...state, caps: { ...state.caps, [event.edge_id]: event.caps } };
    case "log": {
      const seq = state.seq + 1;
      return { ...state, seq, logs: capped(state.logs, { seq, line: event.line }, LOG_LIMIT) };
    }
    case "instances":
      return { ...state, instances: { ...state.instances, [event.slot]: event.instances } };
    case "property":
      return {
        ...state,
        lastProperty: event,
        liveProps: withLiveProperty(state.liveProps, event),
        pending: event.origin === "runtime"
          ? withoutPending(state.pending, event.node_id, liveKey(event.property, event.pad))
          : state.pending,
      };
    default:
      return state;
  }
}

export function liveKey(property: string, pad?: string | null): string {
  return pad ? `${pad}::${property}` : property;
}

/** ``pending`` without the deferred value of ``key`` on ``nodeId``. */
export function withoutPending(pending: LiveProps, nodeId: string, key: string): LiveProps {
  if (!pending[nodeId] || !(key in pending[nodeId])) return pending;
  const props = { ...pending[nodeId] };
  delete props[key];
  const next = { ...pending };
  if (Object.keys(props).length) next[nodeId] = props;
  else delete next[nodeId];
  return next;
}

function withLiveProperty(live: LiveProps, event: PropertyEvent): LiveProps {
  if (!event.ok || event.deferred || event.value === null || event.value === undefined) return live;
  const key = liveKey(event.property, event.pad);
  return { ...live, [event.node_id]: { ...live[event.node_id], [key]: event.value } };
}

export function isActive(state: RuntimeState): boolean {
  return state === "starting" || state === "ready" || state === "paused" || state === "playing" || state === "stopping";
}

/** A worker process exists: after an ERROR it stays alive for inspection. */
export function hasWorker(state: RuntimeState): boolean {
  return isActive(state) || state === "error";
}
