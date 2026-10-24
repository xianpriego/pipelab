import { describe, expect, it } from "vitest";
import { decodeFrame, encodeFrame, pcmFloat32, peakLevels } from "./frames";

describe("preview frames", () => {
  it("round-trips a video frame", () => {
    const payload = new Uint8Array([0xff, 0xd8, 0xff, 0xe0]);
    const buffer = encodeFrame({ kind: "video", node_id: "n3", mime: "image/jpeg", width: 640, height: 360 }, payload);
    const frame = decodeFrame(buffer);
    expect(frame?.header).toEqual({ kind: "video", node_id: "n3", mime: "image/jpeg", width: 640, height: 360 });
    expect(Array.from(frame?.payload ?? [])).toEqual([0xff, 0xd8, 0xff, 0xe0]);
  });

  it("reads the header length as big endian", () => {
    const header = new TextEncoder().encode(JSON.stringify({ kind: "audio", node_id: "a", rate: 48000, channels: 2, format: "F32LE" }));
    const buffer = new ArrayBuffer(4 + header.length + 8);
    const view = new DataView(buffer);
    view.setUint32(0, header.length, false);
    new Uint8Array(buffer, 4).set(header);
    view.setFloat32(4 + header.length, 0.5, true);
    view.setFloat32(8 + header.length, -1, true);
    const frame = decodeFrame(buffer);
    expect(frame?.header.kind).toBe("audio");
    expect(Array.from(pcmFloat32(frame!.payload))).toEqual([0.5, -1]);
  });

  it("rejects truncated or malformed frames", () => {
    expect(decodeFrame(new ArrayBuffer(2))).toBeNull();
    const buffer = new ArrayBuffer(8);
    new DataView(buffer).setUint32(0, 100, false);
    expect(decodeFrame(buffer)).toBeNull();
    const bad = encodeFrame({ kind: "video", node_id: "x", mime: "", width: 0, height: 0 }, new Uint8Array());
    new Uint8Array(bad, 4, 1).set([0x58]);
    expect(decodeFrame(bad)).toBeNull();
    const unknown = encodeFrame({ kind: "text", node_id: "x" } as never, new Uint8Array());
    expect(decodeFrame(unknown)).toBeNull();
  });

  it("computes per-channel peaks", () => {
    expect(peakLevels(new Float32Array([0.1, -0.8, 0.5, 0.2]), 2)).toEqual([0.5, 0.800000011920929]);
    expect(peakLevels(new Float32Array([2]), 1)).toEqual([1]);
  });
});
