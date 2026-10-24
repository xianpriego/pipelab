import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import type { Graph } from "../api/types";
import { node } from "../test/fixtures";
import { useGraphStore } from "../store/graphStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { RestartHint } from "./RestartHint";

const graph: Graph = { nodes: [node("a", "videotestsrc")], edges: [] };

describe("RestartHint", () => {
  beforeEach(() => {
    useGraphStore.getState().load(graph);
    useRuntimeStore.getState().reset();
  });

  it("stays hidden while the running graph matches", () => {
    useRuntimeStore.setState({ state: "playing", runningGraph: graph });
    render(<RestartHint />);
    expect(screen.queryByText(/restart/i)).toBeNull();
  });

  it("appears after a structural edit while running", () => {
    useRuntimeStore.setState({ state: "playing", runningGraph: graph });
    useGraphStore.getState().load({ ...graph, nodes: [...graph.nodes, node("b", "fakesink")] });
    render(<RestartHint />);
    expect(screen.getByRole("button", { name: /restart/i })).toBeTruthy();
  });
});
