import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Issue } from "../../api/types";
import { useGraphStore } from "../../store/graphStore";
import { useUiStore } from "../../store/uiStore";
import { useValidationStore } from "../../store/validationStore";
import { node } from "../../test/fixtures";
import { IssuesPanel } from "./IssuesPanel";

const issue = (patch: Partial<Issue>): Issue => ({
  id: "x", rule: "tee-queue", severity: "warning", message: "Add a queue", node_ids: [], edge_ids: [],
  suggestions: [], ...patch,
});

describe("IssuesPanel", () => {
  beforeEach(() => {
    useGraphStore.getState().load({ nodes: [node("t", "tee", { name: "splitter" })], edges: [] });
    useValidationStore.getState().setIssues([]);
  });
  afterEach(() => vi.restoreAllMocks());

  it("shows an empty state when the graph is valid", () => {
    render(<IssuesPanel />);
    expect(screen.getByText("No issues")).toBeInTheDocument();
  });

  it("groups issues by severity", () => {
    useValidationStore.getState().setIssues([
      issue({ id: "1", severity: "error", message: "Caps are incompatible" }),
      issue({ id: "2", severity: "info", message: "Consider a capsfilter" }),
    ]);
    render(<IssuesPanel />);
    expect(screen.getByText("Errors (1)")).toBeInTheDocument();
    expect(screen.getByText("Suggestions (1)")).toBeInTheDocument();
    expect(screen.queryByText(/Warnings/)).not.toBeInTheDocument();
  });

  it("selects the node of an issue", () => {
    useValidationStore.getState().setIssues([issue({ node_ids: ["t"] })]);
    render(<IssuesPanel />);
    fireEvent.click(screen.getByText("splitter"));
    expect(useUiStore.getState().selectedNodes).toEqual(["t"]);
  });

  it("applies a suggestion through the API", async () => {
    const fixed = { nodes: [node("t", "tee"), node("q", "queue")], edges: [] };
    const applyFix = vi.spyOn(api, "applyFix").mockResolvedValue(fixed);
    const fix = { kind: "insert_on_edge" as const, edge_id: "e1", elements: [{ factory: "queue", properties: {} }] };
    useValidationStore.getState().setIssues([issue({ suggestions: [{ title: "Insert queue", description: "", fix }] })]);
    render(<IssuesPanel />);
    fireEvent.click(screen.getByText("Insert queue"));
    await waitFor(() => expect(useGraphStore.getState().graph.nodes).toHaveLength(2));
    expect(applyFix).toHaveBeenCalledWith(expect.objectContaining({ nodes: expect.any(Array) }), fix);
  });
});
