"""Applies machine-readable fixes (``Fix``) produced by link checks and rules."""

from __future__ import annotations

from pipelab.graph.analyzer import Analyzer
from pipelab.graph.caps_flow import QUEUE_LIKE
from pipelab.graph.editing import (
    add_edge,
    add_node,
    make_room,
    positions_between,
    remove_edge,
)
from pipelab.graph.models import Fix, FixElement, Graph, Node, PadRef, Position
from pipelab.graph.pads import pick_pad, resolve_pad_name


class FixError(ValueError):
    pass


def apply_fix(analyzer: Analyzer, graph: Graph, fix: Fix) -> Graph:
    """Return a new graph with ``fix`` applied."""
    result = graph.model_copy(deep=True)
    handler = _HANDLERS.get(fix.kind)
    if handler is None:
        raise FixError(f"unsupported fix '{fix.kind}'")
    handler(analyzer, result, fix)
    return result


def _node(graph: Graph, node_id: str | None) -> Node:
    node = graph.node(node_id or "")
    if node is None:
        raise FixError(f"node '{node_id}' does not exist")
    return node


def _chain(
    analyzer: Analyzer, graph: Graph, source: PadRef, target: PadRef, elements: list[FixElement]
) -> None:
    """Create ``elements`` and link source → elements… → target."""
    src_node, dst_node = _node(graph, source.node_id), _node(graph, target.node_id)
    make_room(graph, src_node, dst_node, len(elements))
    previous = src_node
    previous_pad, _ = resolve_pad_name(analyzer.catalog, graph, src_node, source.pad, "src")
    for element, position in zip(elements, positions_between(src_node, dst_node, len(elements)), strict=True):
        node = add_node(graph, element.factory, position, element.properties)
        flow = analyzer.flow(graph)
        sink_pad = pick_pad(
            analyzer.catalog, graph, node, "sink", flow.output_caps(previous.id, previous_pad)
        )
        if sink_pad is None:
            raise FixError(f"'{element.factory}' has no input pad")
        add_edge(graph, previous.id, previous_pad, node.id, sink_pad)
        src_pad = pick_pad(analyzer.catalog, graph, node, "src")
        if src_pad is None:
            raise FixError(f"'{element.factory}' has no output pad")
        previous, previous_pad = node, src_pad
    target_pad, _ = resolve_pad_name(analyzer.catalog, graph, dst_node, target.pad, "sink")
    add_edge(graph, previous.id, previous_pad, dst_node.id, target_pad)


def _insert_on_edge(analyzer: Analyzer, graph: Graph, fix: Fix) -> None:
    edge_ids = fix.edge_ids or ([fix.edge_id] if fix.edge_id else [])
    if not edge_ids or not fix.elements:
        raise FixError("insert_on_edge needs edges and elements")
    for edge_id in edge_ids:
        edge = graph.edge(edge_id)
        if edge is None:
            raise FixError(f"edge '{edge_id}' does not exist")
        remove_edge(graph, edge_id)
        _chain(
            analyzer,
            graph,
            PadRef(node_id=edge.source, pad=edge.source_pad),
            PadRef(node_id=edge.target, pad=edge.target_pad),
            fix.elements,
        )


def _connect_via(analyzer: Analyzer, graph: Graph, fix: Fix) -> None:
    if fix.source is None or fix.target is None:
        raise FixError("connect_via needs source and target pads")
    if fix.elements:
        _chain(analyzer, graph, fix.source, fix.target, fix.elements)
        return
    target = _node(graph, fix.target.node_id)
    target_pad, _ = resolve_pad_name(analyzer.catalog, graph, target, fix.target.pad, "sink")
    add_edge(graph, fix.source.node_id, fix.source.pad, target.id, target_pad)


def _set_property(_analyzer: Analyzer, graph: Graph, fix: Fix) -> None:
    node = _node(graph, fix.node_id)
    if not fix.property:
        raise FixError("set_property needs a property name")
    if fix.value is None:
        node.properties.pop(fix.property, None)
    else:
        node.properties[fix.property] = fix.value


def _insert_tee(analyzer: Analyzer, graph: Graph, fix: Fix) -> None:
    """Split ``fix.source`` into its existing link(s) plus a new branch to ``fix.target``."""
    if fix.source is None or fix.target is None:
        raise FixError("insert_tee needs source and target pads")
    source = _node(graph, fix.source.node_id)
    existing = [graph.edge(edge_id) for edge_id in fix.edge_ids]
    branches = [PadRef(node_id=e.target, pad=e.target_pad) for e in existing if e is not None]
    for edge in existing:
        if edge is not None:
            remove_edge(graph, edge.id)
    branches.append(fix.target)
    tee = add_node(graph, "tee", Position(x=source.position.x + 220, y=source.position.y))
    add_edge(graph, source.id, fix.source.pad, tee.id, "sink")
    for index, branch in enumerate(branches):
        target = _node(graph, branch.node_id)
        tee_pad = PadRef(node_id=tee.id, pad=f"src_{index}")
        elements = [] if target.factory in QUEUE_LIKE else [FixElement(factory="queue")]
        if elements:
            _chain(analyzer, graph, tee_pad, branch, elements)
        else:
            target_pad, _ = resolve_pad_name(analyzer.catalog, graph, target, branch.pad, "sink")
            add_edge(graph, tee.id, tee_pad.pad, target.id, target_pad)


def _insert_after(analyzer: Analyzer, graph: Graph, fix: Fix) -> None:
    node = _node(graph, fix.node_id)
    edge = next(iter(graph.outgoing(node.id)), None)
    if edge is not None:
        _insert_on_edge(analyzer, graph, Fix(kind="insert_on_edge", edge_id=edge.id, elements=fix.elements))
        return
    previous, pad = node, pick_pad(analyzer.catalog, graph, node, "src")
    for index, element in enumerate(fix.elements):
        position = Position(x=node.position.x + 240 * (index + 1), y=node.position.y)
        created = add_node(graph, element.factory, position, element.properties)
        sink_pad = pick_pad(analyzer.catalog, graph, created, "sink")
        if pad is None or sink_pad is None:
            raise FixError(f"cannot link '{previous.name}' to '{element.factory}'")
        add_edge(graph, previous.id, pad, created.id, sink_pad)
        previous, pad = created, pick_pad(analyzer.catalog, graph, created, "src")


_HANDLERS = {
    "insert_on_edge": _insert_on_edge,
    "connect_via": _connect_via,
    "set_property": _set_property,
    "insert_tee": _insert_tee,
    "insert_after": _insert_after,
}
