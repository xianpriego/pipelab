import { describe, expect, it } from "vitest";
import type { BusEvent } from "../api/events";
import { BUS_LIMIT, LOG_LIMIT, applyRuntimeEvent, initialRuntime, isActive } from "./runtimeReducer";

const bus = (patch: Partial<BusEvent>): BusEvent => ({
  type: "bus", kind: "info", source: "src", node_id: "n1", text: "hello", ...patch,
});

describe("runtime reducer", () => {
  it("tracks state changes", () => {
    const state = applyRuntimeEvent(initialRuntime(), { type: "state", state: "playing" });
    expect(state.state).toBe("playing");
    expect(isActive(state.state)).toBe(true);
    expect(isActive("stopped")).toBe(false);
  });

  it("resets run data when a new run starts", () => {
    let state = applyRuntimeEvent(initialRuntime(), bus({ kind: "error", text: "boom" }));
    state = applyRuntimeEvent(state, { type: "caps", edge_id: "e1", caps: "video/x-raw" });
    state = applyRuntimeEvent(state, { type: "state", state: "starting" });
    expect(state.bus).toEqual([]);
    expect(state.caps).toEqual({});
    expect(state.nodeAlerts).toEqual({});
    expect(state.error).toBeNull();
  });

  it("marks nodes with errors and keeps errors over warnings", () => {
    let state = applyRuntimeEvent(initialRuntime(), bus({ kind: "warning", node_id: "a" }));
    state = applyRuntimeEvent(state, bus({ kind: "error", node_id: "b", text: "not-negotiated" }));
    state = applyRuntimeEvent(state, bus({ kind: "warning", node_id: "b" }));
    expect(state.nodeAlerts).toEqual({ a: "warning", b: "error" });
    expect(state.error).toBe("not-negotiated");
  });

  it("flags EOS", () => {
    expect(applyRuntimeEvent(initialRuntime(), bus({ kind: "eos" })).eos).toBe(true);
  });

  it("caps the bus and log ring buffers", () => {
    let state = initialRuntime();
    for (let i = 0; i < BUS_LIMIT + 5; i += 1) state = applyRuntimeEvent(state, bus({ text: `m${i}` }));
    expect(state.bus).toHaveLength(BUS_LIMIT);
    expect(state.bus[BUS_LIMIT - 1].text).toBe(`m${BUS_LIMIT + 4}`);
    for (let i = 0; i < LOG_LIMIT + 1; i += 1) state = applyRuntimeEvent(state, { type: "log", line: `l${i}` });
    expect(state.logs).toHaveLength(LOG_LIMIT);
  });

  it("stores stats, caps and property results", () => {
    let state = applyRuntimeEvent(initialRuntime(), {
      type: "stats", time: 1, position: 0.9, duration: null, edges: { e1: { buffers: 30, bytes: 10, fps: 30, bitrate: 80 } },
    });
    state = applyRuntimeEvent(state, { type: "caps", edge_id: "e1", caps: "audio/x-raw" });
    state = applyRuntimeEvent(state, { type: "property", node_id: "n1", property: "volume", value: 0.5, ok: true, error: null });
    expect(state.stats?.edges.e1.fps).toBe(30);
    expect(state.caps.e1).toBe("audio/x-raw");
    expect(state.lastProperty?.property).toBe("volume");
  });

  it("keeps live property values, including runtime-originated ones, until the next start", () => {
    let state = applyRuntimeEvent(initialRuntime(), {
      type: "property", node_id: "sel", property: "active-pad", value: "sink_0", ok: true, error: null, origin: "runtime",
    });
    state = applyRuntimeEvent(state, {
      type: "property", node_id: "mix", property: "xpos", value: 10, ok: true, error: null, pad: "sink_1",
    });
    state = applyRuntimeEvent(state, {
      type: "property", node_id: "sel", property: "active-pad", value: null, ok: false, error: "nope",
    });
    expect(state.liveProps).toEqual({ sel: { "active-pad": "sink_0" }, mix: { "sink_1::xpos": 10 } });
    expect(applyRuntimeEvent(state, { type: "state", state: "starting" }).liveProps).toEqual({});
  });

  it("marks links named by bus errors", () => {
    let state = applyRuntimeEvent(initialRuntime(), bus({ kind: "warning", edge_id: "e1" }));
    state = applyRuntimeEvent(state, bus({ kind: "error", edge_id: "e2", text: "not-negotiated" }));
    state = applyRuntimeEvent(state, bus({ kind: "warning", edge_id: "e2" }));
    expect(state.edgeAlerts).toEqual({ e1: "warning", e2: "error" });
    expect(applyRuntimeEvent(state, { type: "state", state: "starting" }).edgeAlerts).toEqual({});
  });
});
