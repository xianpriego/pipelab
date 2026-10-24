import { describe, expect, it } from "vitest";
import type { Graph } from "../api/types";
import { node } from "../test/fixtures";
import { graphSignature, withLiveProperty } from "./graphSignature";

const graph: Graph = {
  nodes: [node("a", "videotestsrc"), node("b", "fakesink")],
  edges: [{ id: "e1", source: "a", source_pad: "src", target: "b", target_pad: "sink" }],
};

describe("graphSignature", () => {
  it("ignores positions and ordering", () => {
    const moved: Graph = {
      nodes: [{ ...graph.nodes[1], position: { x: 500, y: 9 } }, graph.nodes[0]],
      edges: graph.edges,
    };
    expect(graphSignature(moved)).toBe(graphSignature(graph));
  });

  it("changes with structure and properties", () => {
    expect(graphSignature({ ...graph, edges: [] })).not.toBe(graphSignature(graph));
    const changed = withLiveProperty(graph, "a", "pattern", "ball");
    expect(graphSignature(changed)).not.toBe(graphSignature(graph));
    expect(changed.nodes[0].properties).toEqual({ pattern: "ball" });
  });

  it("tracks live pad property changes", () => {
    const changed = withLiveProperty(graph, "b", "xpos", 10, "sink_0");
    expect(changed.nodes[1].pad_properties).toEqual({ sink_0: { xpos: 10 } });
  });
});
