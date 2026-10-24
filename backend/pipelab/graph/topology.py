"""Graph traversal helpers: reachability, cycles and topological order."""

from __future__ import annotations

from collections import deque

from pipelab.graph.models import Graph


def reaches(graph: Graph, start: str, goal: str, skip_edge: str | None = None) -> bool:
    """Whether ``goal`` is reachable from ``start`` following edge directions."""
    if start == goal:
        return True
    seen, pending = {start}, deque([start])
    while pending:
        current = pending.popleft()
        for edge in graph.edges:
            if edge.id == skip_edge or edge.source != current or edge.target in seen:
                continue
            if edge.target == goal:
                return True
            seen.add(edge.target)
            pending.append(edge.target)
    return False


def _kahn(graph: Graph) -> list[str]:
    """Acyclic part of the graph in topological order (canvas order on ties)."""
    indegree = {node.id: 0 for node in graph.nodes}
    for edge in graph.edges:
        if edge.target in indegree and edge.source in indegree:
            indegree[edge.target] += 1
    position = {node.id: (node.position.x, node.position.y) for node in graph.nodes}
    ready = sorted((n for n, d in indegree.items() if d == 0), key=position.__getitem__)
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for edge in graph.edges:
            if edge.source == current and edge.target in indegree:
                indegree[edge.target] -= 1
                if indegree[edge.target] == 0:
                    ready.append(edge.target)
        ready.sort(key=position.__getitem__)
    return order


def topological_order(graph: Graph) -> list[str]:
    """All node ids, sources first; nodes inside cycles are appended at the end."""
    order = _kahn(graph)
    done = set(order)
    return order + [node.id for node in graph.nodes if node.id not in done]


def cyclic_nodes(graph: Graph) -> list[str]:
    done = set(_kahn(graph))
    return [node.id for node in graph.nodes if node.id not in done]
