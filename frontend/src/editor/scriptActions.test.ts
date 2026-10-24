import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/client";
import type { Project } from "../api/types";
import { useGraphStore } from "../store/graphStore";
import { useProjectStore } from "../store/projectStore";
import { useRecipeStore } from "../store/recipeStore";
import { useRuntimeStore } from "../store/runtimeStore";
import { useUiStore } from "../store/uiStore";
import { node } from "../test/fixtures";
import { applyLiveProperty, selectActivePad } from "./actions";
import { addKeyframeSwitch, parseTriggerValue, triggerScript } from "./scriptActions";

const project: Project = {
  id: "p1", name: "P", description: "", created_at: "", updated_at: "", settings: { gst_debug: "*:2" },
  graph: { nodes: [], edges: [] },
};
const runtimeSwitch = {
  type: "property" as const, node_id: "sel", property: "active-pad", value: "sink_1", ok: true, error: null,
  origin: "runtime" as const,
};

describe("script actions and deferred changes", () => {
  beforeEach(() => {
    useProjectStore.getState().open(project);
    useGraphStore.getState().load({ nodes: [node("sel", "input-selector")], edges: [] });
    useUiStore.setState({ toasts: [] });
    useRuntimeStore.getState().reset();
    useRecipeStore.setState({ recipes: [], state: "idle", error: null });
  });
  afterEach(() => vi.restoreAllMocks());

  it("marks a deferred change as pending without overwriting the graph", async () => {
    useGraphStore.getState().setProperty("sel", "active-pad", "sink_1");
    vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: true, deferred: true, value: "sink_0" });
    expect(await applyLiveProperty({ node_id: "sel", property: "active-pad", value: "sink_1" })).toBe("deferred");
    expect(useRuntimeStore.getState().pending.sel["active-pad"]).toBe("sink_1");
    expect(useGraphStore.getState().graph.nodes[0].properties["active-pad"]).toBe("sink_1");
  });

  it("keeps showing the old pad on the selector until the switch happens", async () => {
    useRuntimeStore.setState({ state: "playing", liveProps: { sel: { "active-pad": "sink_0" } } });
    vi.spyOn(api, "runtimeSetProperty").mockResolvedValue({ ok: true, deferred: true, value: "sink_0" });
    await selectActivePad("sel", "sink_1");
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_0");
    expect(useRuntimeStore.getState().pending.sel["active-pad"]).toBe("sink_1");
    useRuntimeStore.getState().apply(runtimeSwitch);
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_1");
    expect(useRuntimeStore.getState().pending).toEqual({});
  });

  it("is not left pending when the switch was reported before the answer", async () => {
    useRuntimeStore.setState({ state: "playing", liveProps: { sel: { "active-pad": "sink_0" } } });
    vi.spyOn(api, "runtimeSetProperty").mockImplementation(async () => {
      useRuntimeStore.getState().apply(runtimeSwitch);
      return { ok: true, deferred: true, value: "sink_0" };
    });
    await selectActivePad("sel", "sink_1");
    expect(useRuntimeStore.getState().pending).toEqual({});
    expect(useRuntimeStore.getState().liveProps.sel["active-pad"]).toBe("sink_1");
  });

  it("adds the keyframe-switch recipe to a selector", async () => {
    vi.spyOn(api, "scriptRecipes").mockResolvedValue([
      { id: "keyframe-switch", name: "Switch on keyframe", description: "", target_kind: "node",
        factories: ["input-selector"], code: "def on_property(ctx, name, value):\n    return True\n" },
    ]);
    const script = await addKeyframeSwitch("sel");
    expect(script).toMatchObject({ name: "Switch on keyframe", target: { kind: "node", id: "sel" }, enabled: true });
    expect(useGraphStore.getState().graph.scripts).toHaveLength(1);
  });

  it("triggers scripts and reports failures", async () => {
    const script = { id: "s1", name: "Gate", enabled: true, target: { kind: "edge" as const, id: "e1" }, code: "" };
    const trigger = vi.spyOn(api, "runtimeTrigger").mockResolvedValue({ ok: false, error: "no on_trigger" });
    expect(await triggerScript(script, 3)).toBe(false);
    expect(trigger).toHaveBeenCalledWith("p1", "s1", 3);
    expect(useUiStore.getState().toasts[0]).toMatchObject({ level: "error", message: "no on_trigger" });
  });

  it("parses trigger values", () => {
    expect(parseTriggerValue("")).toBeNull();
    expect(parseTriggerValue(" 12 ")).toBe(12);
    expect(parseTriggerValue("-0.5")).toBe(-0.5);
    expect(parseTriggerValue("true")).toBe(true);
    expect(parseTriggerValue("sink_1")).toBe("sink_1");
    expect(parseTriggerValue("1e")).toBe("1e");
  });
});
