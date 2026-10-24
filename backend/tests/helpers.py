"""Compact builders for test graphs."""

from __future__ import annotations

from pipelab.graph.models import Edge, Graph, Node


def chain(*specs: str | tuple[str, dict], pads: dict[int, tuple[str, str]] | None = None) -> Graph:
    """Linear graph ``n0 ! n1 ! …``; ``pads`` overrides (src, sink) pads of link i."""
    nodes = []
    for index, spec in enumerate(specs):
        factory, properties = (spec, {}) if isinstance(spec, str) else spec
        nodes.append(Node(id=f"n{index}", factory=factory, name=f"{factory}{index}", properties=properties))
    edges = []
    for index in range(len(nodes) - 1):
        src_pad, sink_pad = (pads or {}).get(index, ("src", "sink"))
        edges.append(
            Edge(
                id=f"e{index}",
                source=f"n{index}",
                source_pad=src_pad,
                target=f"n{index + 1}",
                target_pad=sink_pad,
            )
        )
    return Graph(nodes=nodes, edges=edges)


def graph(
    nodes: list[tuple[str, str] | tuple[str, str, dict]], edges: list[tuple[str, str, str, str]]
) -> Graph:
    """Graph from ``(id, factory[, properties])`` nodes and ``(src, pad, dst, pad)`` edges."""
    built = []
    for spec in nodes:
        node_id, factory, *rest = spec
        built.append(Node(id=node_id, factory=factory, name=node_id, properties=rest[0] if rest else {}))
    links = [
        Edge(id=f"e{i}", source=s, source_pad=sp, target=t, target_pad=tp)
        for i, (s, sp, t, tp) in enumerate(edges)
    ]
    return Graph(nodes=built, edges=links)
