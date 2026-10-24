"""Low level graph edits (in place) shared by fixes, grouping and the importer."""

from __future__ import annotations

from pipelab.catalog.models import PropertyValue
from pipelab.graph.models import Edge, Graph, Node, Position


def new_node_id(graph: Graph) -> str:
    used = {node.id for node in graph.nodes}
    index = len(graph.nodes) + 1
    while f"n{index}" in used:
        index += 1
    return f"n{index}"


def new_edge_id(graph: Graph) -> str:
    used = {edge.id for edge in graph.edges}
    index = len(graph.edges) + 1
    while f"e{index}" in used:
        index += 1
    return f"e{index}"


def default_name(base: str, taken: set[str]) -> str:
    """GStreamer's naming: ``queue0``, ``queue1``…, and ``avdec_h264-0`` after a digit."""
    separator = "-" if base[-1:].isdigit() else ""
    index = 0
    while f"{base}{separator}{index}" in taken:
        index += 1
    return f"{base}{separator}{index}"


def unique_name(graph: Graph, base: str) -> str:
    """The first ``default_name`` of ``base`` not used by a node of ``graph``."""
    return default_name(base, {node.name for node in graph.nodes})


def add_node(
    graph: Graph,
    factory: str,
    position: Position,
    properties: dict[str, PropertyValue] | None = None,
    name: str | None = None,
) -> Node:
    node = Node(
        id=new_node_id(graph),
        factory=factory,
        name=name or unique_name(graph, factory),
        properties=dict(properties or {}),
        position=position,
    )
    graph.nodes.append(node)
    return node


def add_edge(graph: Graph, source: str, source_pad: str, target: str, target_pad: str) -> Edge:
    edge = Edge(
        id=new_edge_id(graph), source=source, source_pad=source_pad, target=target, target_pad=target_pad
    )
    graph.edges.append(edge)
    return edge


def remove_edge(graph: Graph, edge_id: str) -> None:
    graph.edges = [edge for edge in graph.edges if edge.id != edge_id]


def downstream(graph: Graph, node_id: str) -> set[str]:
    seen, pending = {node_id}, [node_id]
    while pending:
        current = pending.pop()
        for edge in graph.outgoing(current):
            if edge.target not in seen:
                seen.add(edge.target)
                pending.append(edge.target)
    return seen


def make_room(graph: Graph, source: Node, target: Node, slots: int, slot_width: float = 240.0) -> None:
    """Shift ``target`` and everything after it right so ``slots`` nodes fit before it."""
    needed = source.position.x + (slots + 1) * slot_width - target.position.x
    if needed <= 0:
        return
    shifted = downstream(graph, target.id) - downstream(graph, source.id) | {target.id}
    for node in graph.nodes:
        if node.id in shifted:
            node.position = Position(x=node.position.x + needed, y=node.position.y)


def positions_between(source: Node, target: Node, count: int) -> list[Position]:
    dx = (target.position.x - source.position.x) / (count + 1)
    dy = (target.position.y - source.position.y) / (count + 1)
    return [
        Position(x=source.position.x + dx * (i + 1), y=source.position.y + dy * (i + 1)) for i in range(count)
    ]
