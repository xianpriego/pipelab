import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { useGraphStore } from "../store/graphStore";
import { usePreviewStore } from "../store/previewStore";
import { useProjectStore } from "../store/projectStore";
import { useUiStore } from "../store/uiStore";
import { node } from "../test/fixtures";
import { useProbeStore } from "../store/probeStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { reportLinkResult, selectActivePad, sendLiveProperty, setLinkProbe, setLinkTap } from "./actions";

const project: Project = {
  id: "p1", name: "P", description: "", created_at: "", updated_at: "", settings: { gst_debug: "*:2" },
  graph: { nodes: [], edges: [] },
};

describe("editor actions", () => {
  beforeEach(() => {
    useProjectStore.getState().open(project);
    useGraphStore.getState().load({ nodes: [node("sel", "input-selector")], edges: [] });
    useUiStore.setState({ toasts: [] });
    usePreviewStore.setState({ previews: {}, taps: [] });
    useRuntimeStore.getState().reset();
    useProbeStore.getState().reset();
  });
  afterEach(() => vi.restoreAllMocks());

  it("stores the value actually in effect after a live change", async () => {
    vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: true, value: "sink_1" });
    await sendLiveProperty({ node_id: "sel", property: "active-pad", value: "sink_9" });
    expect(useGraphStore.getState().graph.nodes[0].properties["active-pad"]).toBe("sink_1");
  });

  it("reports rejected live changes", async () => {
    vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: false, error: "not changeable in PLAYING" });
    await sendLiveProperty({ node_id: "sel", property: "sync-mode", value: "clock" });
    expect(useUiStore.getState().toasts[0]).toMatchObject({ level: "error", message: "not changeable in PLAYING" });
  });

  it("enables a link tap and opens the preview tab", async () => {
    const tap = vi.spyOn(api, "runtimeTap").mockResolvedValue({ ok: true });
    await setLinkTap("e1", true);
    expect(tap).toHaveBeenCalledWith("p1", "e1", true);
    expect(usePreviewStore.getState().taps).toEqual(["e1"]);
    expect(useUiStore.getState().dockTab).toBe("preview");
  });

  it("does not mark a tap active when the backend refuses it", async () => {
    vi.spyOn(api, "runtimeTap").mockResolvedValue({ ok: false, error: "pipeline not running" });
    await setLinkTap("e1", true);
    expect(usePreviewStore.getState().taps).toEqual([]);
    expect(useUiStore.getState().toasts[0].message).toBe("pipeline not running");
  });

  it("turns 'connect via' suggestions into 'insert on edge' once the link exists", () => {
    const fix = { kind: "connect_via" as const, elements: [{ factory: "videoconvert", properties: {} }] };
    const applyFix = vi.spyOn(api, "applyFix").mockResolvedValue({ nodes: [], edges: [] });
    reportLinkResult({
      allowed: true, severity: "info", source_caps: "", target_caps: "", common_caps: null,
      edge: { id: "e5", source: "a", source_pad: "src", target: "b", target_pad: "sink" },
      issues: [{ id: "i", rule: "safety-converter", severity: "info", message: "m", node_ids: [], edge_ids: [],
        suggestions: [{ title: "Insert videoconvert", description: "", fix }] }],
    });
    useUiStore.getState().toasts[0].actions?.[0].run();
    expect(applyFix).toHaveBeenCalledWith(expect.anything(), {
      kind: "insert_on_edge", edge_id: "e5", elements: fix.elements,
    });
  });

  it("selects a selector pad in the graph only while stopped", async () => {
    const live = vi.spyOn(api, "runtimeSetProperty");
    await selectActivePad("sel", "sink_1");
    expect(useGraphStore.getState().graph.nodes[0].properties["active-pad"]).toBe("sink_1");
    expect(live).not.toHaveBeenCalled();
  });

  it("switches the active pad live and shows it at once while running", async () => {
    useRuntimeStore.setState({ state: "playing", liveProps: { sel: { "active-pad": "sink_0" } } });
    const live = vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: true, value: "sink_1" });
    const pending = selectActivePad("sel", "sink_1");
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_1");
    await pending;
    expect(live).toHaveBeenCalledWith("p1", { node_id: "sel", property: "active-pad", value: "sink_1" });
  });

  it("restores the live value when the switch is refused", async () => {
    useRuntimeStore.setState({ state: "playing", liveProps: { sel: { "active-pad": "sink_0" } } });
    vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: false, error: "no such pad" });
    await selectActivePad("sel", "sink_7");
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_0");
  });

  it("probes a link and opens the probe tab", async () => {
    const probe = vi.spyOn(api, "runtimeProbe").mockResolvedValue({ ok: true });
    await setLinkProbe("e3", true);
    expect(probe).toHaveBeenCalledWith("p1", "e3", true);
    expect(useProbeStore.getState().probed).toEqual(["e3"]);
    expect(useUiStore.getState().dockTab).toBe("probe");
    await setLinkProbe("e3", false);
    expect(useProbeStore.getState().probed).toEqual([]);
  });
});
