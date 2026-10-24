import { describe, expect, it } from "vitest";
import { applySelection } from "../editor/canvas/selection";
import { compatHint } from "./compat";
import { previewKind } from "./elementKinds";
import { formatBitrate, formatBytes, formatClock } from "./format";
import { uniqueName } from "./ids";
import { cleanLaunchLine, parsePipelabJson } from "./importDoc";
import { mediaKind } from "./mediaKind";
import { summary } from "../test/fixtures";

describe("helpers", () => {
  it("hints media compatibility", () => {
    expect(compatHint(["video/x-raw"], ["video/x-raw(memory:CUDAMemory)"])).toBe("compatible");
    expect(compatHint(["video/x-raw"], ["video/x-h264"])).toBe("convertible");
    expect(compatHint(["ANY"], ["audio/x-raw"])).toBe("compatible");
    expect(compatHint([], ["audio/x-raw"])).toBe("unknown");
  });

  it("detects previewable sinks", () => {
    expect(previewKind(summary("autovideosink", { preview: "video" }))).toBe("video");
    expect(previewKind(summary("pulsesink", { preview: "audio" }))).toBe("audio");
    expect(previewKind(summary("filesink"))).toBeNull();
    expect(previewKind(undefined)).toBeNull();
  });

  it("formats numbers", () => {
    expect(formatBytes(1536)).toBe("1.5 KiB");
    expect(formatBitrate(2_500_000)).toBe("2.5 Mbps");
    expect(formatClock(3725)).toBe("1:02:05");
    expect(formatClock(null)).toBe("--:--");
  });

  it("makes unique names", () => {
    expect(uniqueName("queue", ["queue0", "queue1"])).toBe("queue2");
    expect(uniqueName("queue3", [])).toBe("queue0");
  });

  it("parses Pipelab JSON documents", () => {
    const graph = { nodes: [], edges: [] };
    expect(parsePipelabJson(JSON.stringify({ format: "pipelab/graph@1", name: "A", graph }))).toEqual({ name: "A", graph });
    expect(parsePipelabJson(JSON.stringify(graph))).toEqual({ name: null, graph });
    expect(() => parsePipelabJson("{")).toThrow("not valid JSON");
    expect(() => parsePipelabJson("{}")).toThrow("No Pipelab graph");
  });

  it("joins shell continuations", () => {
    expect(cleanLaunchLine("gst-launch-1.0 a \\\n ! b")).toBe("gst-launch-1.0 a   ! b");
  });

  it("chooses media players", () => {
    expect(mediaKind("out.mp4")).toBe("video");
    expect(mediaKind("live/playlist.m3u8")).toBe("hls");
    expect(mediaKind("snap.JPG")).toBe("image");
    expect(mediaKind("blob", "audio/ogg")).toBe("audio");
  });

  it("applies selection changes", () => {
    const current = ["a"];
    expect(applySelection(current, [{ type: "position", id: "a" }])).toBe(current);
    expect(applySelection(current, [{ type: "select", id: "b", selected: true }])).toEqual(["a", "b"]);
    expect(applySelection(current, [{ type: "select", id: "a", selected: false }])).toEqual([]);
    expect(applySelection(current, [{ type: "select", id: "a", selected: true }])).toBe(current);
  });
});
