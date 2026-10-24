import { beforeEach, describe, expect, it } from "vitest";
import { freePosition } from "../lib/graphOps";
import { useGraphStore } from "./graphStore";

const store = () => useGraphStore.getState();

describe("graphStore", () => {
  beforeEach(() => store().load({ nodes: [], edges: [] }));

  it("adds nodes with unique GStreamer-style names", () => {
    const a = store().addNode("videotestsrc", { x: 0, y: 0 });
    const b = store().addNode("videotestsrc", { x: 10, y: 0 });
    expect(a.name).toBe("videotestsrc0");
    expect(b.name).toBe("videotestsrc1");
    expect(store().graph.nodes).toHaveLength(2);
  });

  it("removes nodes together with their edges", () => {
    const a = store().addNode("videotestsrc", { x: 0, y: 0 });
    const b = store().addNode("fakesink", { x: 0, y: 0 });
    store().addEdge({ id: "e1", source: a.id, source_pad: "src", target: b.id, target_pad: "sink" });
    store().removeElements([a.id], []);
    expect(store().graph.nodes.map((n) => n.id)).toEqual([b.id]);
    expect(store().graph.edges).toEqual([]);
  });

  it("undoes and redoes edits", () => {
    const a = store().addNode("queue", { x: 0, y: 0 });
    store().setProperty(a.id, "max-size-buffers", 10);
    expect(store().graph.nodes[0].properties).toEqual({ "max-size-buffers": 10 });
    store().undo();
    expect(store().graph.nodes[0].properties).toEqual({});
    store().undo();
    expect(store().graph.nodes).toHaveLength(0);
    store().redo();
    store().redo();
    expect(store().graph.nodes[0].properties).toEqual({ "max-size-buffers": 10 });
  });

  it("clears the redo stack on a new edit", () => {
    store().addNode("queue", { x: 0, y: 0 });
    store().undo();
    store().addNode("tee", { x: 0, y: 0 });
    expect(store().future).toHaveLength(0);
  });

  it("removes a property when reset to undefined", () => {
    const a = store().addNode("queue", { x: 0, y: 0 });
    store().setProperty(a.id, "leaky", "downstream");
    store().setProperty(a.id, "leaky", undefined);
    expect(store().graph.nodes[0].properties).toEqual({});
  });

  it("stores pad properties per pad and drops empty pads", () => {
    const a = store().addNode("compositor", { x: 0, y: 0 });
    store().setPadProperty(a.id, "sink_0", "xpos", 320);
    expect(store().graph.nodes[0].pad_properties).toEqual({ sink_0: { xpos: 320 } });
    store().setPadProperty(a.id, "sink_0", "xpos", undefined);
    expect(store().graph.nodes[0].pad_properties).toEqual({});
  });

  it("pastes copied nodes with new ids, names and internal edges", () => {
    const a = store().addNode("videotestsrc", { x: 0, y: 0 });
    const b = store().addNode("fakesink", { x: 100, y: 0 });
    store().addEdge({ id: "e1", source: a.id, source_pad: "src", target: b.id, target_pad: "sink" });
    store().copy([a.id, b.id]);
    const pasted = store().paste();
    const { nodes, edges } = store().graph;
    expect(pasted).toHaveLength(2);
    expect(nodes).toHaveLength(4);
    expect(new Set(nodes.map((n) => n.name)).size).toBe(4);
    const copy = edges.find((edge) => edge.id !== "e1");
    expect(copy && pasted.includes(copy.source) && pasted.includes(copy.target)).toBe(true);
    expect(nodes.find((n) => n.id === pasted[0])?.position).toEqual({ x: 40, y: 40 });
  });

  it("refuses duplicate names on rename", () => {
    const a = store().addNode("queue", { x: 0, y: 0 });
    store().addNode("queue", { x: 0, y: 0 });
    expect(store().renameNode(a.id, "queue1")).toBe(false);
    expect(store().renameNode(a.id, "buffer")).toBe(true);
    expect(store().graph.nodes[0].name).toBe("buffer");
  });

  it("moves nodes without recording history until a checkpoint", () => {
    const a = store().addNode("queue", { x: 0, y: 0 });
    const before = store().past.length;
    store().checkpoint();
    store().moveNodes({ [a.id]: { x: 50, y: 60 } });
    store().moveNodes({ [a.id]: { x: 70, y: 80 } });
    expect(store().past.length).toBe(before + 1);
    store().undo();
    expect(store().graph.nodes[0].position).toEqual({ x: 0, y: 0 });
  });

  it("finds a free spot below occupied positions", () => {
    store().addNode("queue", { x: 0, y: 0 });
    store().addNode("queue", { x: 0, y: 110 });
    expect(freePosition(store().graph, { x: 10, y: 10 })).toEqual({ x: 10, y: 230 });
    expect(freePosition(store().graph, { x: 500, y: 0 })).toEqual({ x: 500, y: 0 });
  });
});
