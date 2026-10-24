import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { tapKey } from "../api/events";
import { subscribeAudio } from "../lib/audioBus";
import { usePreviewStore } from "./previewStore";

const store = () => usePreviewStore.getState();

describe("previewStore", () => {
  beforeEach(() => {
    let n = 0;
    vi.stubGlobal("URL", { ...URL, createObjectURL: vi.fn(() => `blob:${(n += 1)}`), revokeObjectURL: vi.fn() });
    usePreviewStore.setState({ previews: {}, taps: [] });
  });
  afterEach(() => vi.unstubAllGlobals());

  it("keeps the latest video frame per sink and revokes the previous URL", () => {
    const header = { kind: "video" as const, node_id: "n1", mime: "image/jpeg", width: 320, height: 240 };
    store().handleFrame({ header, payload: new Uint8Array([1]) }, 0);
    store().handleFrame({ header, payload: new Uint8Array([2]) }, 100);
    const preview = store().previews.n1;
    expect(preview.kind === "video" && preview.url).toBe("blob:2");
    expect(preview.kind === "video" && preview.frames).toBe(2);
    expect(preview.kind === "video" && Math.round(preview.fps)).toBe(10);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:1");
  });

  it("stores link taps under edge:<id> and publishes audio samples", () => {
    const listener = vi.fn();
    const unsubscribe = subscribeAudio(tapKey("e7"), listener);
    const samples = new Float32Array([0.5, -0.25]);
    store().handleFrame({
      header: { kind: "audio", node_id: tapKey("e7"), edge_id: "e7", rate: 48000, channels: 2, format: "F32LE" },
      payload: new Uint8Array(samples.buffer),
    });
    unsubscribe();
    expect(listener).toHaveBeenCalledWith(expect.any(Float32Array), 48000, 2);
    expect(store().previews["edge:e7"]).toMatchObject({ kind: "audio", levels: [0.5, 0.25] });
  });

  it("tracks tapped links and removes their previews", () => {
    store().setTapped("e1", true);
    store().setTapped("e1", true);
    store().setTapped("e2", true);
    expect(store().taps).toEqual(["e1", "e2"]);
    store().handleFrame({ header: { kind: "video", node_id: "edge:e1", mime: "", width: 1, height: 1 }, payload: new Uint8Array() });
    store().setTapped("e1", false);
    store().remove("edge:e1");
    expect(store().taps).toEqual(["e2"]);
    expect(store().previews["edge:e1"]).toBeUndefined();
    store().clear();
    expect(store().taps).toEqual([]);
  });
});
