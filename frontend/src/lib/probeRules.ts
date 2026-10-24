// No-code probe rule sets: pure operations on the graph and on rule lists.

import type { Action, Condition, ProbeRule, ProbeRuleSet, ProbeTarget, Trigger } from "../api/dynamic";
import type { Graph } from "../api/types";
import { newId } from "./ids";

export function probesOf(graph: Graph): ProbeRuleSet[] {
  return graph.probes ?? [];
}

export function probesFor(graph: Graph, kind: ProbeTarget["kind"], id: string): ProbeRuleSet[] {
  return probesOf(graph).filter((probe) => probe.target.kind === kind && probe.target.id === id);
}

export function createRuleSet(target: ProbeTarget, name: string): ProbeRuleSet {
  return { id: newId("p"), name, enabled: true, target, variables: {}, rules: [] };
}

export function newRule(when: Trigger = { type: "buffer" }): ProbeRule {
  return { id: newId("r"), when, conditions: [], actions: [] };
}

export function addProbe(graph: Graph, probe: ProbeRuleSet): Graph {
  return { ...graph, probes: [...probesOf(graph), probe] };
}

export function updateProbe(graph: Graph, id: string, patch: Partial<Omit<ProbeRuleSet, "id">>): Graph {
  return { ...graph, probes: probesOf(graph).map((probe) => (probe.id === id ? { ...probe, ...patch } : probe)) };
}

export function removeProbe(graph: Graph, id: string): Graph {
  return { ...graph, probes: probesOf(graph).filter((probe) => probe.id !== id) };
}

/** Rule sets whose element or link still exists. */
export function liveProbes(graph: Graph, probes: ProbeRuleSet[] = probesOf(graph)): ProbeRuleSet[] {
  const nodes = new Set(graph.nodes.map((node) => node.id));
  const edges = new Set(graph.edges.map((edge) => edge.id));
  return probes.filter((probe) => (probe.target.kind === "node" ? nodes : edges).has(probe.target.id));
}

/** Copies re-targeted through the id maps (dropped when their target was not copied). */
export function retargetProbes(
  probes: ProbeRuleSet[], nodeIds: Map<string, string>, edgeIds: Map<string, string>,
): ProbeRuleSet[] {
  return probes.flatMap((probe) => {
    const id = (probe.target.kind === "node" ? nodeIds : edgeIds).get(probe.target.id);
    return id ? [{ ...probe, id: newId("p"), target: { ...probe.target, id } }] : [];
  });
}

/** Moves the item at ``from`` to ``to`` (both clamped), returning a new list. */
export function moveItem<T>(items: T[], from: number, to: number): T[] {
  if (from < 0 || from >= items.length) return items;
  const target = Math.max(0, Math.min(items.length - 1, to));
  if (target === from) return items;
  const next = items.slice();
  const [item] = next.splice(from, 1);
  next.splice(target, 0, item);
  return next;
}

export function replaceAt<T>(items: T[], index: number, item: T): T[] {
  return items.map((current, i) => (i === index ? item : current));
}

export function removeAt<T>(items: T[], index: number): T[] {
  return items.filter((_item, i) => i !== index);
}

export function updateRule(probe: ProbeRuleSet, ruleId: string, patch: Partial<Omit<ProbeRule, "id">>): ProbeRuleSet {
  return { ...probe, rules: probe.rules.map((rule) => (rule.id === ruleId ? { ...rule, ...patch } : rule)) };
}

/** A fresh condition/action of ``type`` (fields filled by the editor). */
export function blankCondition(type: Condition["type"]): Condition {
  return type === "every" ? { type, n: 2 } : type === "random" ? { type, percent: 5 } : { type };
}

export function blankAction(type: Action["type"]): Action {
  return { type };
}

/** Distinct signal names a rule set reacts to. */
export function signalNames(probe: ProbeRuleSet): string[] {
  const names = probe.rules
    .filter((rule) => rule.when.type === "signal" && rule.when.name)
    .map((rule) => rule.when.name as string);
  return [...new Set(names)];
}

/** Badge summary per target (`node:<id>` / `edge:<id>`). */
export interface ProbeMarker {
  names: string[];
  enabled: boolean;
}

export function probeMarkers(graph: Graph): Record<string, ProbeMarker> {
  const markers: Record<string, ProbeMarker> = {};
  for (const probe of probesOf(graph)) {
    const key = `${probe.target.kind}:${probe.target.id}`;
    const marker = markers[key] ?? { names: [], enabled: false };
    markers[key] = { names: [...marker.names, probe.name], enabled: marker.enabled || probe.enabled };
  }
  return markers;
}

/** One-line description of a rule ("When idle 2000 ms → post-message, log"). */
export function ruleSummary(rule: ProbeRule): string {
  const detail = rule.when.ms ? ` ${rule.when.ms} ms` : rule.when.event ? ` ${rule.when.event}`
    : rule.when.property ? ` ${rule.when.property}` : rule.when.name ? ` ${rule.when.name}` : "";
  const ifs = rule.conditions.length ? ` if ${rule.conditions.map((c) => (c.negate ? `not ${c.type}` : c.type)).join(" & ")}` : "";
  const thens = rule.actions.map((a) => a.type).join(", ") || "nothing";
  return `When ${rule.when.type}${detail}${ifs} → ${thens}`;
}
