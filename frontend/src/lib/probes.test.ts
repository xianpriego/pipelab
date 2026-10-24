import { describe, expect, it } from "vitest";
import type { ProbeBuffer, ProbeEvent } from "../api/events";
import { emptyProbeData, ingestProbe, summarize } from "./probes";

const buffer = (time: number, patch: Partial<ProbeBuffer> = {}): ProbeBuffer => ({
  kind: "buffer", time, pts: time, dts: null, duration: 0.04, size: 1000, flags: [], offset: null, ...patch,
});
const batch = (edgeId: string, items: ProbeEvent["items"], dropped = 0): ProbeEvent => ({
  type: "probe", edge_id: edgeId, dropped, items,
});

describe("probe reducer", () => {
  it("appends batches with increasing sequence numbers", () => {
    let data = ingestProbe(emptyProbeData(), batch("e1", [buffer(0), buffer(0.04)]), false);
    data = ingestProbe(data, batch("e2", [{ kind: "event", time: 0.05, event: "eos", detail: "" }]), false);
    expect(data.rows.map((row) => [row.seq, row.edgeId])).toEqual([[1, "e1"], [2, "e1"], [3, "e2"]]);
  });

  it("caps the number of rows keeping the newest", () => {
    let data = emptyProbeData();
    for (let i = 0; i < 5; i += 1) data = ingestProbe(data, batch("e1", [buffer(i)]), false, 3);
    expect(data.rows.map((row) => row.item.time)).toEqual([2, 3, 4]);
  });

  it("ignores items while paused but keeps counting drops", () => {
    const data = ingestProbe(emptyProbeData(), batch("e1", [buffer(0), buffer(1)], 7), true);
    expect(data.rows).toEqual([]);
    expect(data.skipped).toBe(2);
    expect(data.dropped).toEqual({ e1: 7 });
  });
});

describe("probe summary", () => {
  it("computes rate, average size and key frame interval", () => {
    const items = Array.from({ length: 61 }, (_, i) =>
      buffer(i / 30, { size: i % 30 === 0 ? 5000 : 1000, flags: i % 30 === 0 ? [] : ["delta-unit"] }),
    );
    const data = ingestProbe(emptyProbeData(), batch("e1", items), false);
    const summary = summarize(data.rows, "e1");
    expect(summary.buffers).toBe(61);
    expect(summary.perSecond).toBeCloseTo(30, 5);
    expect(summary.keyframeInterval).toBeCloseTo(1, 5);
    expect(summary.avgSize).toBeGreaterThan(1000);
  });

  it("has no key frame interval for raw streams", () => {
    const data = ingestProbe(emptyProbeData(), batch("e1", [buffer(0), buffer(0.1)]), false);
    expect(summarize(data.rows, "e1").keyframeInterval).toBeNull();
    expect(summarize(data.rows, "other").buffers).toBe(0);
  });
});
