import { beforeEach, describe, expect, it } from "vitest";
import { createScript } from "../lib/scripts";
import { node } from "../test/fixtures";
import { useGraphStore } from "./graphStore";

const base = () => ({
  nodes: [node("a", "videotestsrc"), node("b", "fakesink")],
  edges: [{ id: "e1", source: "a", source_pad: "src", target: "b", target_pad: "sink" }],
});

describe("graph store scripts", () => {
  beforeEach(() => useGraphStore.getState().load(base()));

  it("adds, edits and removes scripts with undo", () => {
    const store = useGraphStore.getState();
    const script = createScript({ kind: "edge", id: "e1" }, "Gate", "");
    store.addScript(script);
    useGraphStore.getState().updateScript(script.id, { code: "x = 1" });
    expect(useGraphStore.getState().graph.scripts?.[0].code).toBe("x = 1");
    useGraphStore.getState().undo();
    expect(useGraphStore.getState().graph.scripts?.[0].code).toBe("");
    useGraphStore.getState().removeScript(script.id);
    expect(useGraphStore.getState().graph.scripts).toEqual([]);
  });

  it("removes the scripts of deleted nodes and of the links that go with them", () => {
    const store = useGraphStore.getState();
    store.addScript(createScript({ kind: "node", id: "a" }, "on a", ""));
    useGraphStore.getState().addScript(createScript({ kind: "edge", id: "e1" }, "on e1", ""));
    useGraphStore.getState().addScript(createScript({ kind: "node", id: "b" }, "on b", ""));
    useGraphStore.getState().removeElements(["a"], []);
    expect(useGraphStore.getState().graph.scripts?.map((s) => s.name)).toEqual(["on b"]);
  });

  it("removes the scripts of a deleted link", () => {
    useGraphStore.getState().addScript(createScript({ kind: "edge", id: "e1" }, "on e1", ""));
    useGraphStore.getState().removeElements([], ["e1"]);
    expect(useGraphStore.getState().graph.scripts).toEqual([]);
  });

  it("copies node and inner link scripts on paste, re-targeted to the new ids", () => {
    useGraphStore.getState().addScript(createScript({ kind: "node", id: "a" }, "on a", "code"));
    useGraphStore.getState().addScript(createScript({ kind: "edge", id: "e1" }, "on e1", ""));
    useGraphStore.getState().copy(["a", "b"]);
    const pasted = useGraphStore.getState().paste();
    const graph = useGraphStore.getState().graph;
    const newEdge = graph.edges.find((edge) => edge.source === pasted[0]);
    const scripts = graph.scripts ?? [];
    expect(scripts).toHaveLength(4);
    expect(scripts.filter((s) => s.target.id === pasted[0])).toMatchObject([{ name: "on a", code: "code" }]);
    expect(scripts.filter((s) => s.target.id === newEdge?.id)).toMatchObject([{ name: "on e1" }]);
  });

  it("does not copy link scripts when only one end is copied", () => {
    useGraphStore.getState().addScript(createScript({ kind: "edge", id: "e1" }, "on e1", ""));
    useGraphStore.getState().copy(["a"]);
    useGraphStore.getState().paste();
    expect(useGraphStore.getState().graph.scripts).toHaveLength(1);
  });
});
