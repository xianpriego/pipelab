"""Automatic left-to-right layered layout for graphs without positions."""

from __future__ import annotations

from pipelab.graph.models import Graph, Position
from pipelab.graph.topology import topological_order

COLUMN_WIDTH = 280.0
ROW_HEIGHT = 150.0


def _layers(graph: Graph) -> dict[str, int]:
    """Longest path from any source: a node sits right of all its producers."""
    layer = {node.id: 0 for node in graph.nodes}
    for node_id in topological_order(graph):
        for edge in graph.outgoing(node_id):
            if edge.target in layer and edge.target != node_id:
                layer[edge.target] = max(layer[edge.target], layer[node_id] + 1)
    return layer


def auto_layout(graph: Graph) -> Graph:
    """Return a copy of ``graph`` with every node placed on a grid."""
    layer = _layers(graph)
    order = topological_order(graph)
    columns: dict[int, list[str]] = {}
    row: dict[str, float] = {}
    for node_id in order:
        columns.setdefault(layer[node_id], []).append(node_id)
    for index in sorted(columns):

        def barycenter(node_id: str) -> float:
            parents = [row[e.source] for e in graph.incoming(node_id) if e.source in row]
            return sum(parents) / len(parents) if parents else float(order.index(node_id))

        ranked = sorted(columns[index], key=barycenter)
        for position, node_id in enumerate(ranked):
            row[node_id] = float(position)
    nodes = [
        node.model_copy(
            update={"position": Position(x=layer[node.id] * COLUMN_WIDTH, y=row[node.id] * ROW_HEIGHT)}
        )
        for node in graph.nodes
    ]
    return graph.model_copy(update={"nodes": nodes})
