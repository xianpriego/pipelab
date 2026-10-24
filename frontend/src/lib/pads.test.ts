import { describe, expect, it } from "vitest";
import { node, pad } from "../test/fixtures";
import { computeHandles, findTemplate, templateRegex } from "./pads";

const edge = (id: string, source: string, sourcePad: string, target: string, targetPad: string) => ({
  id, source, source_pad: sourcePad, target, target_pad: targetPad,
});

describe("pads", () => {
  it("matches template names", () => {
    expect(templateRegex("sink_%u").test("sink_12")).toBe(true);
    expect(templateRegex("sink_%u").test("sink_x")).toBe(false);
    expect(templateRegex("recv_rtp_sink_%u_%u_%u").test("recv_rtp_sink_0_1_2")).toBe(true);
    expect(templateRegex("src_%s").test("src_video")).toBe(true);
  });

  it("finds the template of concrete pads", () => {
    const pads = [pad("src", "src", "always"), pad("video_%u", "sink", "request"), pad("audio_%u", "sink", "request")];
    expect(findTemplate(pads, "audio_3")?.name).toBe("audio_%u");
    expect(findTemplate(pads, "src")?.name).toBe("src");
    expect(findTemplate(pads, "other")).toBeUndefined();
  });

  it("creates one handle per always pad", () => {
    const handles = computeHandles([pad("sink", "sink", "always"), pad("src", "src", "always")], node("q", "queue"), []);
    expect(handles.sinks.map((h) => h.id)).toEqual(["sink"]);
    expect(handles.srcs.map((h) => [h.id, h.kind])).toEqual([["src", "always"]]);
  });

  it("lists used request pads plus a 'new pad' handle", () => {
    const pads = [pad("sink_%u", "sink", "request", ["video/x-raw"]), pad("src", "src", "always")];
    const edges = [edge("e1", "a", "src", "c", "sink_1"), edge("e2", "b", "src", "c", "sink_0")];
    const handles = computeHandles(pads, node("c", "compositor"), edges);
    expect(handles.sinks.map((h) => [h.id, h.kind])).toEqual([
      ["sink_0", "request"],
      ["sink_1", "request"],
      ["sink_%u", "request-new"],
    ]);
    expect(handles.sinks[2].label).toBe("+ sink_%u");
    expect(handles.sinks[0].mediaTypes).toEqual(["video/x-raw"]);
  });

  it("keeps sometimes templates and concrete dynamic pads", () => {
    const pads = [pad("sink", "sink", "always"), pad("video_%u", "src", "sometimes"), pad("audio_%u", "src", "sometimes")];
    const edges = [edge("e1", "d", "video_%u", "q1", "sink"), edge("e2", "d", "audio_0", "q2", "sink")];
    const handles = computeHandles(pads, node("d", "qtdemux"), edges);
    expect(handles.srcs.map((h) => [h.id, h.kind])).toEqual([
      ["video_%u", "sometimes"],
      ["audio_%u", "sometimes"],
      ["audio_0", "sometimes"],
    ]);
  });

  it("keeps orphan pads of unknown elements so edges still render", () => {
    const handles = computeHandles(undefined, node("x", "missing"), [edge("e1", "x", "src_7", "y", "sink")]);
    expect(handles.srcs.map((h) => [h.id, h.kind])).toEqual([["src_7", "orphan"]]);
  });
});
