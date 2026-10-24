// Probe scripts: pure helpers on the graph and on recipes.

import type { Graph, Issue, ProbeScript, ScriptRecipe, ScriptTarget } from "../api/types";
import { newId } from "./ids";

export const BLANK_SCRIPT = `# Probe script. Every callback is optional; delete the ones you do not need.
# Watched pads: a link script watches the link's source pad, an element script
# its sink pads (set WATCH = "src" or "all" to change that).


def setup(ctx):
    """Called once, before the pipeline starts."""


def on_buffer(ctx, pad, buffer):
    """Every buffer on the watched pads. Return DROP to drop it."""
    return PASS


def on_event(ctx, pad, event):
    """Every downstream event (caps, segment, eos…) on the watched pads."""
    return PASS


def on_trigger(ctx, value):
    """Called by the Trigger button of the inspector."""
    ctx.log(f"triggered with {value!r}")
`;

export function scriptsOf(graph: Graph): ProbeScript[] {
  return graph.scripts ?? [];
}

export function scriptsFor(graph: Graph, kind: ScriptTarget["kind"], id: string): ProbeScript[] {
  return scriptsOf(graph).filter((script) => script.target.kind === kind && script.target.id === id);
}

export function createScript(target: ScriptTarget, name: string, code: string): ProbeScript {
  return { id: newId("s"), name, enabled: true, target, code };
}

export function addScript(graph: Graph, script: ProbeScript): Graph {
  return { ...graph, scripts: [...scriptsOf(graph), script] };
}

export function updateScript(graph: Graph, id: string, patch: Partial<Omit<ProbeScript, "id">>): Graph {
  return { ...graph, scripts: scriptsOf(graph).map((script) => (script.id === id ? { ...script, ...patch } : script)) };
}

export function removeScript(graph: Graph, id: string): Graph {
  return { ...graph, scripts: scriptsOf(graph).filter((script) => script.id !== id) };
}

/** Scripts whose element or link still exists. */
export function liveScripts(graph: Graph, scripts: ProbeScript[] = scriptsOf(graph)): ProbeScript[] {
  const nodes = new Set(graph.nodes.map((node) => node.id));
  const edges = new Set(graph.edges.map((edge) => edge.id));
  return scripts.filter((script) => (script.target.kind === "node" ? nodes : edges).has(script.target.id));
}

/** Copies of ``scripts`` re-targeted through the id maps (dropped when their target is not copied). */
export function retargetScripts(
  scripts: ProbeScript[], nodeIds: Map<string, string>, edgeIds: Map<string, string>,
): ProbeScript[] {
  return scripts.flatMap((script) => {
    const map = script.target.kind === "node" ? nodeIds : edgeIds;
    const id = map.get(script.target.id);
    return id ? [{ ...script, id: newId("s"), target: { ...script.target, id } }] : [];
  });
}

const TRIGGER = /^def on_trigger\(/m;

/** Whether the script reacts to the Trigger button. */
export function hasTrigger(code: string): boolean {
  return TRIGGER.test(code);
}

/** Recipes applicable to a target: same kind and, if restricted, the element's factory. */
export function recipesFor(recipes: ScriptRecipe[], kind: ScriptTarget["kind"], factory?: string): ScriptRecipe[] {
  return recipes.filter(
    (recipe) =>
      recipe.target_kind === kind &&
      (recipe.factories.length === 0 || (factory !== undefined && recipe.factories.includes(factory))),
  );
}

/**
 * Validation issues of rule "script" about ``script``: they target its element or link and
 * read "Script '<name>': …" (an id mentioning the script also matches).
 */
export function scriptIssues(issues: Issue[], script: ProbeScript): Issue[] {
  const prefix = `Script '${script.name}'`;
  return issues.filter((issue) => {
    if (issue.rule !== "script") return false;
    if (issue.id.split(":").includes(script.id)) return true;
    const targets = script.target.kind === "node" ? issue.node_ids : issue.edge_ids;
    return targets.includes(script.target.id) && issue.message.startsWith(prefix);
  });
}

/** Human name of what a script is attached to. */
export function targetLabel(graph: Graph, target: ScriptTarget): string {
  const nodeName = (id: string) => graph.nodes.find((node) => node.id === id)?.name ?? id;
  if (target.kind === "node") return nodeName(target.id);
  const edge = graph.edges.find((e) => e.id === target.id);
  if (!edge) return target.id;
  return `${nodeName(edge.source)}.${edge.source_pad} → ${nodeName(edge.target)}.${edge.target_pad}`;
}

/** Badge summary for canvas markers: names of the scripts and whether any is enabled. */
export interface ScriptMarker {
  names: string[];
  enabled: boolean;
}

export function scriptMarkers(graph: Graph): Record<string, ScriptMarker> {
  const markers: Record<string, ScriptMarker> = {};
  for (const script of scriptsOf(graph)) {
    const key = `${script.target.kind}:${script.target.id}`;
    const marker = markers[key] ?? { names: [], enabled: false };
    markers[key] = { names: [...marker.names, script.name], enabled: marker.enabled || script.enabled };
  }
  return markers;
}

/** Lines mentioned by validation messages ("… line 12 …"). */
export function issueLines(issues: Issue[]): number[] {
  return issues.flatMap((issue) => [...issue.message.matchAll(/\bline (\d+)/gi)].map((match) => Number(match[1])));
}
