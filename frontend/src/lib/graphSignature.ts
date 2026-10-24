// Structural fingerprint of a graph: what a running pipeline was built from.

import type { Graph, PropertyValue } from "../api/types";

/** Everything that changes the built pipeline (positions do not). */
export function graphSignature(graph: Graph): string {
  const nodes = [...graph.nodes]
    .map(({ id, factory, name, properties, pad_properties, preview }) => ({
      id, factory, name, preview, properties: sorted(properties), pad_properties: sortedPads(pad_properties),
    }))
    .sort((a, b) => a.id.localeCompare(b.id));
  const edges = [...graph.edges]
    .map(({ source, source_pad, target, target_pad }) => `${source}.${source_pad}>${target}.${target_pad}`)
    .sort();
  return JSON.stringify({ nodes, edges });
}

/** The graph as it is running after a property was changed live. */
export function withLiveProperty(
  graph: Graph, nodeId: string, property: string, value: PropertyValue, pad?: string | null,
): Graph {
  const nodes = graph.nodes.map((node) => {
    if (node.id !== nodeId) return node;
    if (!pad) return { ...node, properties: { ...node.properties, [property]: value } };
    const padProps = { ...(node.pad_properties[pad] ?? {}), [property]: value };
    return { ...node, pad_properties: { ...node.pad_properties, [pad]: padProps } };
  });
  return { ...graph, nodes };
}

function sorted(record: Record<string, PropertyValue>): [string, PropertyValue][] {
  return Object.entries(record).sort(([a], [b]) => a.localeCompare(b));
}

function sortedPads(record: Record<string, Record<string, PropertyValue>>): [string, [string, PropertyValue][]][] {
  return Object.entries(record)
    .map(([pad, props]) => [pad, sorted(props)] as [string, [string, PropertyValue][]])
    .sort(([a], [b]) => a.localeCompare(b));
}
