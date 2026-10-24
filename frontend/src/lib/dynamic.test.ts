import { describe, expect, it } from "vitest";
import type { Slot } from "../api/dynamic";
import type { Graph } from "../api/types";
import { node, prop } from "../test/fixtures";
import { callArgs, signature, typedArg } from "./apiFunctions";
import { exposeParam, exposePort, paramOf, pruneDefinition, renamePort, slugify, suggestPortName } from "./components";
import * as ops from "./graphOps";
import { addProbe, liveProbes, moveItem, probeMarkers, signalNames } from "./probeRules";
import { PROBE_TEMPLATES, templatesFor } from "./probeTemplates";
import { scoped, scopedId, scopePrefix } from "./scope";
import { addInitialInstance, builtinFunctions, createSlot, nextInstanceId, slotNames } from "./slots";
import { formatValue, isReference, matchSuggestions, parseValue, referenceSuggestions, unknownReference } from "./valueRefs";

const graph = (): Graph => ({
  nodes: [node("src", "videotestsrc"), node("sink", "fakesink")],
  edges: [{ id: "e1", source: "src", source_pad: "src", target: "sink", target_pad: "sink" }],
});

describe("$ references", () => {
  it("parses typed text into values", () => {
    expect(parseValue("")).toBeNull();
    expect(parseValue("42")).toBe(42);
    expect(parseValue("-1.5e3")).toBe(-1500);
    expect(parseValue("true")).toBe(true);
    expect(parseValue("$count")).toBe("$count");
    expect(parseValue("sink_1")).toBe("sink_1");
    expect(formatValue(null)).toBe("");
    expect(formatValue(false)).toBe("false");
  });

  it("tells references from escaped dollars", () => {
    expect(isReference("$x")).toBe(true);
    expect(isReference("$$x")).toBe(false);
    expect(isReference("$")).toBe(false);
    expect(isReference(3)).toBe(false);
  });

  it("suggests variables, arguments and builtins (with or without their $)", () => {
    const scope = {
      variables: ["count"], params: ["location"],
      builtins: [{ name: "$value", description: "trigger value" }, { name: "pts", description: "pts" }],
    };
    const all = referenceSuggestions(scope);
    expect(all.map((s) => s.text)).toEqual(["$count", "$location", "$value", "$pts"]);
    expect(matchSuggestions("$c", all).map((s) => s.text)).toEqual(["$count"]);
    expect(matchSuggestions("count", all)).toEqual([]);
    expect(matchSuggestions("$$c", all)).toEqual([]);
    expect(unknownReference("$nope", scope)).toBe("$nope");
    expect(unknownReference("$value", scope)).toBeNull();
    expect(unknownReference("plain", scope)).toBeNull();
  });
});

describe("rule lists", () => {
  it("moves items for reordering", () => {
    expect(moveItem(["a", "b", "c"], 0, 2)).toEqual(["b", "c", "a"]);
    expect(moveItem(["a", "b", "c"], 2, 0)).toEqual(["c", "a", "b"]);
    expect(moveItem(["a", "b"], 0, 5)).toEqual(["b", "a"]);
    expect(moveItem(["a", "b"], 3, 0)).toEqual(["a", "b"]);
  });
});

describe("probe templates", () => {
  it("builds a watchdog that posts branch-down and branch-up", () => {
    const watchdog = PROBE_TEMPLATES.find((t) => t.id === "watchdog");
    const probe = watchdog?.build({ kind: "edge", id: "e1" }, {});
    expect(probe?.target).toEqual({ kind: "edge", id: "e1" });
    expect(probe?.rules.map((r) => r.when.type)).toEqual(["idle", "resumed"]);
    expect(probe?.rules[0].actions[0]).toMatchObject({ type: "post-message", name: "branch-down" });
    expect(probe?.rules[1].actions[0]).toMatchObject({ type: "post-message", name: "branch-up" });
  });

  it("gives every template fresh ids and filters by target and factory", () => {
    for (const template of PROBE_TEMPLATES) {
      const target = { kind: template.kinds[0], id: "x" };
      const a = template.build(target, { nodeName: "sel" });
      const b = template.build(target, { nodeName: "sel" });
      expect(a.id).not.toBe(b.id);
      expect(a.rules.length).toBeGreaterThan(0);
    }
    const names = (kind: "node" | "edge", factory?: string) => templatesFor(kind, factory).map((t) => t.id);
    expect(names("node", "input-selector")).toContain("keyframe-switch");
    expect(names("node", "queue")).not.toContain("keyframe-switch");
    expect(names("edge")).toContain("watchdog");
    expect(names("edge")).not.toContain("keyframe-switch");
  });

  it("lists the signals a probe reacts to and marks targets", () => {
    const gate = PROBE_TEMPLATES.find((t) => t.id === "gate")?.build({ kind: "edge", id: "e1" }, {});
    expect(gate && signalNames(gate).length).toBeGreaterThan(0);
    const marked = probeMarkers(addProbe(graph(), gate ?? PROBE_TEMPLATES[0].build({ kind: "edge", id: "e1" }, {})));
    expect(marked["edge:e1"].enabled).toBe(true);
  });
});

describe("cascades", () => {
  it("drops probes with their element or link but keeps slots for validation", () => {
    let g = addProbe(graph(), PROBE_TEMPLATES[0].build({ kind: "edge", id: "e1" }, {}));
    g = addProbe(g, PROBE_TEMPLATES[0].build({ kind: "node", id: "sink" }, {}));
    g = { ...g, slots: [createSlot("cam", [{ port: "src", node_id: "sink", pad: "sink", pad_properties: {} }])] };
    const after = ops.removeElements(g, ["sink"], []);
    expect(after.probes).toEqual([]);
    expect(after.slots).toHaveLength(1);
    expect(liveProbes(after, g.probes)).toEqual([]);
  });
});

describe("components", () => {
  it("slugifies names and suggests port names", () => {
    expect(slugify("RTSP input #1")).toBe("rtsp-input-1");
    expect(suggestPortName("sink_%u", [])).toBe("sink");
    expect(suggestPortName("src", ["src"])).toBe("src_1");
  });

  it("keeps port names unique and one port per pad", () => {
    let ports = exposePort([], { name: "out", direction: "src", node_id: "n", pad: "src" });
    ports = exposePort(ports, { name: "video", direction: "src", node_id: "n", pad: "src" });
    expect(ports).toEqual([{ name: "video", direction: "src", node_id: "n", pad: "src" }]);
    ports = exposePort(ports, { name: "in", direction: "sink", node_id: "m", pad: "sink" });
    expect(renamePort(ports, "in", "video")).toBeNull();
    expect(renamePort(ports, "in", "input")?.map((p) => p.name)).toEqual(["video", "input"]);
  });

  it("lets one parameter drive several properties and prunes stale targets", () => {
    let params = exposeParam([], "location", { node_id: "a", property: "location" }, "url", "rtsp://");
    params = exposeParam(params, "location", { node_id: "b", property: "uri" });
    params = exposeParam(params, "location", { node_id: "b", property: "uri" });
    expect(params).toHaveLength(1);
    expect(params[0].targets).toHaveLength(2);
    expect(paramOf(params, "b", "uri")).toBe("location");
    expect(paramOf(params, "b", "uri", "sink_0")).toBeUndefined();
    const pruned = pruneDefinition(
      { id: "c", name: "c", description: "", version: 1, graph: { nodes: [], edges: [] },
        ports: [{ name: "p", direction: "src", node_id: "gone", pad: "src" }], parameters: params },
      { nodes: [node("a", "rtspsrc")], edges: [] },
    );
    expect(pruned.ports).toEqual([]);
    expect(pruned.parameters[0].targets).toEqual([{ node_id: "a", property: "location" }]);
  });

  it("scopes runtime ids to the open instance", () => {
    const prefix = scopePrefix(["cam1", "inner"]);
    expect(prefix).toBe("cam1/inner/");
    const record = { "cam1/inner/q": 1, "cam1/inner/deep/q": 2, "cam1/x": 3, top: 4 };
    expect(scoped(record, prefix)).toEqual({ q: 1 });
    expect(scoped(record, "")).toBe(record);
    expect(scopedId("cam1/inner/q", prefix)).toBe("q");
    expect(scopedId("cam1/q", "")).toBeNull();
    expect(scopedId("top", "")).toBe("top");
  });
});

describe("slots", () => {
  it("names functions after the component and numbers instances", () => {
    expect(slotNames("rtsp-input")).toEqual({ item: "rtsp_input", name: "rtsp_inputs" });
    expect(nextInstanceId("cam", ["cam0", "cam2"])).toBe("cam1");
    let slot: Slot = createSlot("cam");
    slot = addInitialInstance(addInitialInstance(slot, { pattern: 1 }));
    expect(slot.initial.map((i) => i.id)).toEqual(["cam0", "cam1"]);
  });

  it("describes built-in functions with typed parameters and an optional id", () => {
    const slot = createSlot("cam");
    const fns = builtinFunctions(slot, [prop("pattern", { type: "enum" }), prop("latency", { type: "uint" }), prop("ro", { writable: false })]);
    expect(fns.map((f) => f.name)).toEqual(["add_cam", "remove_cam", "restart_cam", "list_cams"]);
    expect(signature(fns[0].name, fns[0].params, fns[0].returns)).toBe("add_cam(pattern: str, latency: int, id: str) -> id");
    expect(fns[1].params.map((p) => p.name)).toEqual(["id"]);
  });
});

describe("API call arguments", () => {
  it("types text by the declared parameter type", () => {
    expect(typedArg("int", "12")).toBe(12);
    expect(typedArg("int", "x")).toBeNull();
    expect(typedArg("float", "0.5")).toBe(0.5);
    expect(typedArg("bool", "true")).toBe(true);
    expect(typedArg("bool", "")).toBe(false);
    expect(typedArg("string", " a b ")).toBe(" a b ");
    expect(typedArg("string", "  ")).toBeNull();
  });

  it("uses defaults for untouched fields and omits empty optional ones", () => {
    const params = [
      { name: "location", type: "string" as const },
      { name: "latency", type: "int" as const, default: 200 },
      { name: "id", type: "string" as const, default: null },
    ];
    expect(callArgs(params, { location: "rtsp://cam" })).toEqual({ location: "rtsp://cam", latency: 200 });
    expect(callArgs(params, { latency: "50", id: "" })).toEqual({ latency: 50 });
  });
});
