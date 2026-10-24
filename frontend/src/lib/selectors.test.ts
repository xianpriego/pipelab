import { describe, expect, it } from "vitest";
import type { Graph } from "../api/types";
import { node, pad, summary } from "../test/fixtures";
import { discardedEdges, resolveActivePad, selectorDirection, selectorInfo } from "./selectors";

const inputSelector = summary("input-selector", {
  selectors: ["active-pad"],
  pads: [pad("sink_%u", "sink", "request"), pad("src", "src", "always")],
});
const outputSelector = summary("output-selector", {
  selectors: ["active-pad"],
  pads: [pad("sink", "sink", "always"), pad("src_%u", "src", "request")],
});
const byName = { "input-selector": inputSelector, "output-selector": outputSelector };
const edge = (id: string, source: string, sourcePad: string, target: string, targetPad: string) => ({
  id, source, source_pad: sourcePad, target, target_pad: targetPad,
});

const graph: Graph = {
  nodes: [node("a", "videotestsrc"), node("b", "videotestsrc"), node("sel", "input-selector"), node("out", "fakesink")],
  edges: [
    edge("e0", "b", "src", "sel", "sink_1"),
    edge("e1", "a", "src", "sel", "sink_0"),
    edge("e2", "sel", "src", "out", "sink"),
  ],
};

describe("selectors", () => {
  it("knows which side an element selects from", () => {
    expect(selectorDirection(inputSelector)).toBe("sink");
    expect(selectorDirection(outputSelector)).toBe("src");
    expect(selectorDirection(summary("tee", { pads: [pad("src_%u", "src", "request")] }))).toBeNull();
  });

  it("resolves the active pad: live value, then configuration, then the first pad", () => {
    const sel = graph.nodes[2];
    expect(resolveActivePad(sel, ["sink_0", "sink_1"])).toBe("sink_0");
    const configured = { ...sel, properties: { "active-pad": "sink_1" } };
    expect(resolveActivePad(configured, ["sink_0", "sink_1"])).toBe("sink_1");
    expect(resolveActivePad(configured, ["sink_0", "sink_1"], { "active-pad": "sink_0" })).toBe("sink_0");
    expect(resolveActivePad({ ...sel, properties: { "active-pad": "sink_9" } }, ["sink_0"])).toBe("sink_0");
  });

  it("lists linked request pads by index", () => {
    expect(selectorInfo(graph.nodes[2], inputSelector, graph.edges)).toEqual({
      direction: "sink", pads: ["sink_0", "sink_1"], active: "sink_0",
    });
  });

  it("marks links into inactive pads as discarded", () => {
    expect([...discardedEdges(graph, byName, {})]).toEqual(["e0"]);
    expect([...discardedEdges(graph, byName, { sel: { "active-pad": "sink_1" } })]).toEqual(["e1"]);
  });

  it("handles output-selector source pads", () => {
    const outGraph: Graph = {
      nodes: [node("s", "videotestsrc"), node("o", "output-selector"), node("x", "fakesink"), node("y", "fakesink")],
      edges: [edge("a", "s", "src", "o", "sink"), edge("b", "o", "src_0", "x", "sink"), edge("c", "o", "src_1", "y", "sink")],
    };
    expect([...discardedEdges(outGraph, byName, {})]).toEqual(["c"]);
  });
});
