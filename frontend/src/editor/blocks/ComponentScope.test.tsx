import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { ComponentDef } from "../../api/dynamic";
import type { Graph } from "../../api/types";
import { isDirty, runtimePrefix, sessionGraph, useComponentStore } from "../../store/componentStore";
import { projectGraph, useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { node } from "../../test/fixtures";
import { deleteCurrentComponent, enterInstance, leaveTo } from "./componentActions";
import { ScopeBar } from "./ScopeBar";

const def = (id: string, graph: Graph): ComponentDef => ({
  id, name: id.toUpperCase(), description: "", version: 1, graph, ports: [], parameters: [],
});

const library: Record<string, ComponentDef> = {
  outer: def("outer", { nodes: [node("q", "queue"), node("inner1", "component:inner")], edges: [] }),
  inner: def("inner", { nodes: [node("conv", "videoconvert")], edges: [] }),
};

const project: Graph = { nodes: [node("cam", "component:outer"), node("sink", "fakesink")], edges: [] };

describe("component scopes", () => {
  beforeEach(() => {
    useComponentStore.getState().exitTo(0);
    useGraphStore.getState().load(project);
    useProjectStore.setState({ meta: { id: "p1", name: "Studio" } as never });
    vi.spyOn(api, "getComponent").mockImplementation(async (id) => library[id]);
    vi.spyOn(api, "listComponents").mockResolvedValue(Object.values(library));
    vi.spyOn(api, "catalog").mockResolvedValue([]);
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });
  afterEach(() => vi.restoreAllMocks());

  it("enters nested instances with breadcrumbs and runtime prefixes, and leaves them", async () => {
    render(<ScopeBar />);
    expect(screen.queryByRole("navigation")).toBeNull();
    await enterInstance("cam");
    expect(useGraphStore.getState().graph.nodes.map((n) => n.id)).toEqual(["q", "inner1"]);
    expect(projectGraph()).toBe(project);
    await enterInstance("inner1");
    const crumbs = await screen.findByRole("navigation", { name: "Component breadcrumbs" });
    expect(crumbs).toHaveTextContent("Studio›OUTER›INNER");
    expect(runtimePrefix(useComponentStore.getState().sessions)).toBe("cam/inner1/");

    fireEvent.click(screen.getByRole("button", { name: "OUTER" }));
    expect(useComponentStore.getState().sessions).toHaveLength(1);
    expect(useGraphStore.getState().graph.nodes.map((n) => n.id)).toEqual(["q", "inner1"]);
    fireEvent.click(screen.getByRole("button", { name: "Studio" }));
    expect(useGraphStore.getState().graph).toBe(project);
    expect(screen.queryByRole("navigation")).toBeNull();
  });

  it("refuses to open a component inside itself", async () => {
    await enterInstance("cam");
    useGraphStore.getState().commit({ ...useGraphStore.getState().graph, nodes: [node("again", "component:outer")] });
    expect(await enterInstance("again")).toBe(false);
    expect(useComponentStore.getState().sessions).toHaveLength(1);
  });

  it("tracks unsaved edits, saves the definition and discards changes", async () => {
    const save = vi.spyOn(api, "saveComponent").mockImplementation(async (component) => ({ ...component, version: 2 }));
    render(<ScopeBar />);
    await act(() => enterInstance("cam"));
    const session = () => useComponentStore.getState().sessions[0];
    expect(isDirty(session(), useGraphStore.getState().graph)).toBe(false);
    expect(screen.getByRole("button", { name: /save component/i })).toBeDisabled();

    act(() => void useGraphStore.getState().addNode("identity", { x: 10, y: 10 }));
    await screen.findByText("unsaved");
    fireEvent.click(screen.getByRole("button", { name: /save component/i }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(save.mock.calls[0][0].graph.nodes).toHaveLength(3);
    await waitFor(() => expect(screen.queryByText("unsaved")).toBeNull());
    expect(session().base.version).toBe(2);

    act(() => {
      useComponentStore.getState().update({ name: "Renamed" });
      useGraphStore.getState().removeElements(["q"], []);
    });
    expect(isDirty(session(), sessionGraph(0))).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "Discard" }));
    expect(session().name).toBe("OUTER");
    expect(useGraphStore.getState().graph.nodes).toHaveLength(3);
    expect(isDirty(session(), useGraphStore.getState().graph)).toBe(false);
  });

  it("asks before leaving with unsaved changes", async () => {
    await enterInstance("cam");
    useGraphStore.getState().addNode("identity", { x: 0, y: 0 });
    vi.mocked(window.confirm).mockReturnValue(false);
    expect(leaveTo(0)).toBe(false);
    expect(useComponentStore.getState().sessions).toHaveLength(1);
    vi.mocked(window.confirm).mockReturnValue(true);
    expect(leaveTo(0)).toBe(true);
    expect(useGraphStore.getState().graph).toBe(project);
  });

  it("deletes a component after listing who uses it", async () => {
    const remove = vi.spyOn(api, "deleteComponent").mockResolvedValue(undefined);
    vi.spyOn(api, "componentUsage").mockResolvedValue({ components: [], projects: [{ id: "p1", name: "Studio" }] });
    await enterInstance("cam");
    await enterInstance("inner1");
    vi.mocked(window.confirm).mockReturnValue(false);
    expect(await deleteCurrentComponent()).toBe(false);
    expect(remove).not.toHaveBeenCalled();
    expect(vi.mocked(window.confirm).mock.calls[0][0]).toContain('project "Studio"');
    vi.mocked(window.confirm).mockReturnValue(true);
    expect(await deleteCurrentComponent()).toBe(true);
    expect(remove).toHaveBeenCalledWith("inner");
    expect(useComponentStore.getState().sessions.map((s) => s.base.id)).toEqual(["outer"]);
  });
});
