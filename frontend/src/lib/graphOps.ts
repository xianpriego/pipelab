// Pure, immutable operations on the pipeline graph.

import type { Graph, GraphEdge, GraphNode, Position, PropertyValue } from "../api/types";
import { newId, uniqueName } from "./ids";

export const EMPTY_GRAPH: Graph = { nodes: [], edges: [] };

export function createNode(graph: Graph, factory: string, position: Position): GraphNode {
  return {
    id: newId("n"),
    factory,
    name: uniqueName(factory, graph.nodes.map((n) => n.name)),
    properties: {},
    pad_properties: {},
    position,
    preview: "auto",
  };
}

const NODE_FOOTPRINT = { width: 220, height: 110 };

/** First position at or below ``desired`` that does not overlap an existing node. */
export function freePosition(graph: Graph, desired: Position): Position {
  const overlaps = (p: Position) =>
    graph.nodes.some(
      (node) =>
        Math.abs(node.position.x - p.x) < NODE_FOOTPRINT.width &&
        Math.abs(node.position.y - p.y) < NODE_FOOTPRINT.height,
    );
  let candidate = desired;
  for (let attempt = 0; attempt < 30 && overlaps(candidate); attempt += 1) {
    candidate = { x: desired.x, y: desired.y + (attempt + 1) * NODE_FOOTPRINT.height };
  }
  return candidate;
}

export function addNode(graph: Graph, node: GraphNode): Graph {
  return { ...graph, nodes: [...graph.nodes, node] };
}

export function updateNode(graph: Graph, id: string, patch: Partial<GraphNode>): Graph {
  return { ...graph, nodes: graph.nodes.map((node) => (node.id === id ? { ...node, ...patch } : node)) };
}

function withoutKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  const copy = { ...record };
  delete copy[key];
  return copy;
}

export function setProperty(graph: Graph, nodeId: string, name: string, value: PropertyValue | undefined): Graph {
  const node = graph.nodes.find((n) => n.id === nodeId);
  if (!node) return graph;
  const properties = value === undefined ? withoutKey(node.properties, name) : { ...node.properties, [name]: value };
  return updateNode(graph, nodeId, { properties });
}

export function setPadProperty(
  graph: Graph, nodeId: string, pad: string, name: string, value: PropertyValue | undefined,
): Graph {
  const node = graph.nodes.find((n) => n.id === nodeId);
  if (!node) return graph;
  const current = node.pad_properties[pad] ?? {};
  const next = value === undefined ? withoutKey(current, name) : { ...current, [name]: value };
  const padProperties =
    Object.keys(next).length === 0 ? withoutKey(node.pad_properties, pad) : { ...node.pad_properties, [pad]: next };
  return updateNode(graph, nodeId, { pad_properties: padProperties });
}

export function moveNodes(graph: Graph, positions: Record<string, Position>): Graph {
  return {
    ...graph,
    nodes: graph.nodes.map((node) => (positions[node.id] ? { ...node, position: positions[node.id] } : node)),
  };
}

export function addEdge(graph: Graph, edge: GraphEdge): Graph {
  return { ...graph, edges: [...graph.edges.filter((e) => e.id !== edge.id), edge] };
}

/** Removes nodes and edges, with the links of the removed nodes. */
export function removeElements(graph: Graph, nodeIds: string[], edgeIds: string[]): Graph {
  const nodes = new Set(nodeIds);
  const edges = new Set(edgeIds);
  return {
    ...graph,
    nodes: graph.nodes.filter((node) => !nodes.has(node.id)),
    edges: graph.edges.filter((edge) => !edges.has(edge.id) && !nodes.has(edge.source) && !nodes.has(edge.target)),
  };
}

/** Sub-graph made of the given nodes and the edges between them. */
export function extractSubgraph(graph: Graph, nodeIds: string[]): Graph {
  const ids = new Set(nodeIds);
  return {
    nodes: graph.nodes.filter((node) => ids.has(node.id)),
    edges: graph.edges.filter((edge) => ids.has(edge.source) && ids.has(edge.target)),
  };
}

/** Paste a copied sub-graph with fresh ids and names, shifted by ``offset``. */
export function pasteSubgraph(graph: Graph, clip: Graph, offset: Position): { graph: Graph; nodeIds: string[] } {
  const idMap = new Map<string, string>();
  const names = graph.nodes.map((node) => node.name);
  const nodes = clip.nodes.map((node) => {
    const id = newId("n");
    idMap.set(node.id, id);
    const name = uniqueName(node.factory, names);
    names.push(name);
    return {
      ...node,
      id,
      name,
      position: { x: node.position.x + offset.x, y: node.position.y + offset.y },
    };
  });
  const edges = clip.edges.map((edge) => ({
    ...edge,
    id: newId("e"),
    source: idMap.get(edge.source) ?? edge.source,
    target: idMap.get(edge.target) ?? edge.target,
  }));
  const pasted: Graph = { ...graph, nodes: [...graph.nodes, ...nodes], edges: [...graph.edges, ...edges] };
  return { graph: pasted, nodeIds: nodes.map((node) => node.id) };
}

export function renameNode(graph: Graph, nodeId: string, name: string): Graph | null {
  if (!name || graph.nodes.some((node) => node.name === name && node.id !== nodeId)) return null;
  return updateNode(graph, nodeId, { name });
}
