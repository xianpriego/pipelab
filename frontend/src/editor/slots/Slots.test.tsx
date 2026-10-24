import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../api/client";
import type { Slot } from "../../api/dynamic";
import { createSlot } from "../../lib/slots";
import { useCatalogStore } from "../../store/catalogStore";
import { useGraphStore } from "../../store/graphStore";
import { useProjectStore } from "../../store/projectStore";
import { applyRuntimeEvent, initialRuntime } from "../../store/runtimeReducer";
import { useRuntimeStore } from "../../store/runtimeStore";
import { node, pad, summary } from "../../test/fixtures";
import { CallForm } from "../api/CallForm";
import { addSlotOn, defaultLink } from "./slotActions";
import { slotLinkEdges, slotNodeId, slotPortStats, toSlotNodes } from "./slotFlow";
import { SlotInspector } from "./SlotInspector";

const camSummary = summary("component:cam", { family: "component", pads: [pad("src", "src", "always")] });
const compositor = summary("compositor", { pads: [pad("sink_%u", "sink", "request"), pad("src", "src", "always")] });
const tee = summary("tee", { pads: [pad("sink", "sink", "always"), pad("src_%u", "src", "request")] });
const viewer = summary("component:viewer", { family: "component", pads: [pad("in", "sink", "always")] });

describe("slots", () => {
  beforeEach(() => {
    useGraphStore.getState().load({ nodes: [node("mix", "compositor"), node("t", "tee")], edges: [] });
    useCatalogStore.setState({
      byName: { compositor, tee, "component:cam": camSummary, "component:viewer": viewer }, state: "ready",
    });
    useProjectStore.setState({ meta: { id: "p1", name: "Studio" } as never });
    useRuntimeStore.getState().reset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("links component outputs to request sinks and tees to component inputs", () => {
    const mix = node("mix", "compositor");
    expect(defaultLink(mix, compositor, camSummary)).toEqual({ port: "src", node_id: "mix", pad: "sink_%u", pad_properties: {} });
    expect(defaultLink(node("t", "tee"), tee, viewer)).toEqual({ port: "in", node_id: "t", pad: "src_%u", pad_properties: {} });
    expect(defaultLink(mix, compositor, viewer)).toBeNull();
  });

  it("adds a slot on an element and draws it as a stacked node with dashed links", () => {
    const slot = addSlotOn("mix", "cam");
    const graph = useGraphStore.getState().graph;
    expect(graph.slots).toHaveLength(1);
    const [flowNode] = toSlotNodes(graph, {
      byName: useCatalogStore.getState().byName, live: {}, running: false, selected: new Set(), positions: {}, severities: {},
    });
    expect(flowNode.id).toBe(slotNodeId(slot.id));
    expect(flowNode.data.handles.srcs.map((h) => h.id)).toEqual(["src"]);
    expect(slotLinkEdges(graph, useCatalogStore.getState().byName)).toEqual([{
      id: `slotlink:${slot.id}:0`, source: slotNodeId(slot.id), source_pad: "src", target: "mix", target_pad: "sink_%u",
    }]);
  });

  it("shows the totals of the live instances of each linked port", () => {
    const slot = addSlotOn("mix", "cam");
    const graph = useGraphStore.getState().graph;
    const stat = (fps: number) => ({ buffers: 1, bytes: 1, fps, bitrate: 1000 });
    const stats = { [`${slot.id}.cam0:src`]: stat(30), [`${slot.id}.cam1:src`]: stat(0), "e1": stat(60) };
    expect(slotPortStats(slot.id, "src", stats)).toEqual({ flowing: 1, fps: 30, bitrate: 2000 });
    const context = {
      byName: useCatalogStore.getState().byName, live: {}, selected: new Set<string>(), positions: {}, severities: {}, stats,
    };
    expect(toSlotNodes(graph, { ...context, running: true })[0].data.rates).toEqual([{ port: "src", flowing: 1, fps: 30, bitrate: 2000 }]);
    expect(toSlotNodes(graph, { ...context, running: false })[0].data.rates).toEqual([]);
  });

  it("keeps live instances per slot from runtime events", () => {
    let state = applyRuntimeEvent(initialRuntime(), { type: "instances", slot: "s1", instances: [{ id: "cam0", params: {} }] });
    state = applyRuntimeEvent(state, { type: "instances", slot: "s2", instances: [] });
    state = applyRuntimeEvent(state, {
      type: "instances", slot: "s1", instances: [{ id: "cam0", params: {} }, { id: "cam1", params: { pattern: 1 } }],
    });
    expect(Object.keys(state.instances)).toEqual(["s1", "s2"]);
    expect(state.instances.s1.map((i) => i.id)).toEqual(["cam0", "cam1"]);
  });

  it("lists, removes and restarts live instances while running", async () => {
    const slot: Slot = { ...createSlot("cam"), id: "s1" };
    useGraphStore.getState().addSlot(slot);
    useRuntimeStore.setState({ state: "playing", instances: { s1: [{ id: "cam0", params: { pattern: 1 } }] } });
    vi.spyOn(api, "runtimeInstances").mockResolvedValue({ slots: { s1: [{ id: "cam0", params: { pattern: 1 } }] } });
    const call = vi.spyOn(api, "runtimeCall").mockResolvedValue({ ok: true, result: null });
    render(<SlotInspector slotId="s1" />);
    expect(await screen.findByText("pattern=1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Restart cam0" }));
    await waitFor(() => expect(call).toHaveBeenCalledWith("p1", "restart_cam", { id: "cam0" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove cam0" }));
    await waitFor(() => expect(call).toHaveBeenCalledWith("p1", "remove_cam", { id: "cam0" }));
  });
});

describe("API call form", () => {
  beforeEach(() => {
    useProjectStore.setState({ meta: { id: "p1", name: "Studio" } as never });
    useRuntimeStore.getState().reset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("sends typed arguments and shows the result or the error", async () => {
    const call = vi.spyOn(api, "runtimeCall")
      .mockResolvedValueOnce({ ok: true, result: "cam3" })
      .mockResolvedValueOnce({ ok: false, error: "slot full" });
    vi.spyOn(api, "runtimeInstances").mockResolvedValue({ slots: {} });
    const params = [
      { name: "location", type: "string" as const }, { name: "latency", type: "int" as const, default: 200 },
      { name: "live", type: "bool" as const, default: false },
    ];
    const { rerender } = render(<CallForm name="add_cam" params={params} returns="id" />);
    expect(screen.getByText("add_cam(location: str, latency: int = 200, live: bool = false) -> id")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /call/i })).toBeDisabled();
    useRuntimeStore.setState({ state: "playing" });
    rerender(<CallForm name="add_cam" params={params} returns="id" />);
    fireEvent.change(screen.getByLabelText("Argument location"), { target: { value: "rtsp://cam" } });
    fireEvent.change(screen.getByLabelText("Argument latency"), { target: { value: "50" } });
    fireEvent.click(screen.getByLabelText("Argument live"));
    fireEvent.click(screen.getByRole("button", { name: /call/i }));
    await waitFor(() => expect(call).toHaveBeenCalledWith("p1", "add_cam", { location: "rtsp://cam", latency: 50, live: true }));
    expect(await screen.findByText('"cam3"')).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /call/i }));
    expect(await screen.findByText("slot full")).toBeInTheDocument();
  });
});
