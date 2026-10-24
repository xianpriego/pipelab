import { describe, expect, it } from "vitest";
import type { Graph, Issue, ScriptRecipe } from "../api/types";
import { node } from "../test/fixtures";
import {
  addScript, createScript, hasTrigger, issueLines, liveScripts, recipesFor, removeScript, retargetScripts,
  scriptIssues, scriptMarkers, scriptsFor, targetLabel, updateScript,
} from "./scripts";

const graph: Graph = {
  nodes: [node("sel", "input-selector"), node("sink", "fakesink")],
  edges: [{ id: "e1", source: "sel", source_pad: "src", target: "sink", target_pad: "sink" }],
};

const recipe = (id: string, target_kind: "node" | "edge", factories: string[] = []): ScriptRecipe => ({
  id, name: id, description: "", target_kind, factories, code: "",
});

describe("probe script helpers", () => {
  it("adds, updates and removes scripts", () => {
    const script = createScript({ kind: "node", id: "sel" }, "Switch", "def setup(ctx): pass");
    let next = addScript(graph, script);
    expect(scriptsFor(next, "node", "sel")).toEqual([script]);
    next = updateScript(next, script.id, { enabled: false, name: "Off" });
    expect(next.scripts?.[0]).toMatchObject({ enabled: false, name: "Off", code: script.code });
    expect(removeScript(next, script.id).scripts).toEqual([]);
    expect(graph.scripts).toBeUndefined();
  });

  it("keeps only scripts whose target exists and re-targets copies", () => {
    const onNode = createScript({ kind: "node", id: "sel" }, "a", "");
    const onEdge = createScript({ kind: "edge", id: "e1" }, "b", "");
    const orphan = createScript({ kind: "edge", id: "gone" }, "c", "");
    expect(liveScripts(graph, [onNode, onEdge, orphan])).toEqual([onNode, onEdge]);
    const copies = retargetScripts([onNode, onEdge], new Map([["sel", "sel2"]]), new Map());
    expect(copies).toHaveLength(1);
    expect(copies[0]).toMatchObject({ name: "a", target: { kind: "node", id: "sel2" } });
    expect(copies[0].id).not.toBe(onNode.id);
  });

  it("detects trigger handlers at module level only", () => {
    expect(hasTrigger("x = 1\ndef on_trigger(ctx, value):\n    pass")).toBe(true);
    expect(hasTrigger("    def on_trigger(ctx, value): pass")).toBe(false);
    expect(hasTrigger("def on_buffer(ctx, pad, buffer): pass")).toBe(false);
  });

  it("filters recipes by target kind and factory", () => {
    const recipes = [recipe("keyframe-switch", "node", ["input-selector"]), recipe("custom", "node"), recipe("gate", "edge")];
    expect(recipesFor(recipes, "node", "input-selector").map((r) => r.id)).toEqual(["keyframe-switch", "custom"]);
    expect(recipesFor(recipes, "node", "queue").map((r) => r.id)).toEqual(["custom"]);
    expect(recipesFor(recipes, "edge").map((r) => r.id)).toEqual(["gate"]);
  });

  it("finds the validation issues and lines of a script", () => {
    const issue = (message: string, patch: Partial<Issue> = {}): Issue => ({
      id: "script:x", rule: "script", severity: "error", message, node_ids: ["sel"], edge_ids: [], suggestions: [],
      ...patch,
    });
    const switcher = createScript({ kind: "node", id: "sel" }, "Switch", "");
    const other = createScript({ kind: "node", id: "sel" }, "Other", "");
    const onLink = createScript({ kind: "edge", id: "e1" }, "Switch", "");
    const issues = [
      issue("Script 'Switch': line 3: invalid syntax"),
      issue("Script 'Other': defines no callback"),
      issue("Script 'Switch': line 1: x", { node_ids: [], edge_ids: ["e1"] }),
      issue("unrelated", { rule: "unlinked-pad" }),
    ];
    expect(scriptIssues(issues, switcher).map((i) => i.message)).toEqual(["Script 'Switch': line 3: invalid syntax"]);
    expect(scriptIssues(issues, other)).toHaveLength(1);
    expect(scriptIssues(issues, onLink)).toHaveLength(1);
    expect(scriptIssues([issue("anything", { id: `script:${other.id}`, node_ids: [] })], other)).toHaveLength(1);
    expect(issueLines(scriptIssues(issues, switcher))).toEqual([3]);
  });

  it("labels targets and summarises markers", () => {
    expect(targetLabel(graph, { kind: "edge", id: "e1" })).toBe("sel.src → sink.sink");
    expect(targetLabel(graph, { kind: "node", id: "sel" })).toBe("sel");
    const withScripts = addScript(addScript(graph, { ...createScript({ kind: "node", id: "sel" }, "a", ""), enabled: false }),
      createScript({ kind: "node", id: "sel" }, "b", ""));
    expect(scriptMarkers(withScripts)["node:sel"]).toEqual({ names: ["a", "b"], enabled: true });
  });
});
