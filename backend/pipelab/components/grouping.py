"""Turning a selection into a component, and an instance back into elements."""

from __future__ import annotations

import re

from pipelab.components.models import Component, ComponentPort
from pipelab.graph.editing import new_edge_id, new_node_id, unique_name
from pipelab.graph.models import Edge, Graph, Node, Position

_TEMPLATE_TOKENS = re.compile(r"_?%[uds]")


class GroupingError(ValueError):
    pass


def _port_name(pad: str, taken: set[str]) -> str:
    base = _TEMPLATE_TOKENS.sub("", pad) or "pad"
    name, index = base, 1
    while name in taken:
        name, index = f"{base}_{index}", index + 1
    taken.add(name)
    return name


def _centroid(nodes: list[Node]) -> Position:
    return Position(
        x=sum(n.position.x for n in nodes) / len(nodes), y=sum(n.position.y for n in nodes) / len(nodes)
    )


def _inner_graph(graph: Graph, selected: set[str]) -> Graph:
    nodes = [n.model_copy(deep=True) for n in graph.nodes if n.id in selected]
    left, top = min(n.position.x for n in nodes), min(n.position.y for n in nodes)
    for node in nodes:
        node.position = Position(x=node.position.x - left, y=node.position.y - top)
    edges = [e.model_copy() for e in graph.edges if e.source in selected and e.target in selected]
    inner_edges = {e.id for e in edges}

    def inside(kind: str, target_id: str) -> bool:
        return target_id in (selected if kind == "node" else inner_edges)

    return Graph(
        nodes=nodes,
        edges=edges,
        scripts=[s.model_copy(deep=True) for s in graph.scripts if inside(s.target.kind, s.target.id)],
        probes=[p.model_copy(deep=True) for p in graph.probes if inside(p.target.kind, p.target.id)],
    )


def group_into_component(
    graph: Graph, node_ids: list[str], component_id: str, name: str
) -> tuple[Component, Graph]:
    """Selected nodes become ``component_id``; the returned graph holds an instance instead."""
    selected = {n.id for n in graph.nodes if n.id in set(node_ids)}
    if not selected:
        raise GroupingError("select at least one element")
    inner = _inner_graph(graph, selected)
    ports: list[ComponentPort] = []
    port_of: dict[tuple[str, str, str], str] = {}
    taken: set[str] = set()
    outer = graph.model_copy(deep=True)
    instance = Node(
        id=new_node_id(outer),
        factory=f"component:{component_id}",
        name=unique_name(outer, component_id.replace("-", "_")),
        position=_centroid([n for n in graph.nodes if n.id in selected]),
    )
    for edge in outer.edges:
        crossing_in = edge.target in selected and edge.source not in selected
        crossing_out = edge.source in selected and edge.target not in selected
        if not (crossing_in or crossing_out):
            continue
        node_id, pad, direction = (
            (edge.target, edge.target_pad, "sink") if crossing_in else (edge.source, edge.source_pad, "src")
        )
        key = (node_id, pad, direction)
        if key not in port_of:
            port_of[key] = _port_name(pad, taken)
            ports.append(ComponentPort(name=port_of[key], direction=direction, node_id=node_id, pad=pad))
        if crossing_in:
            edge.target, edge.target_pad = instance.id, port_of[key]
        else:
            edge.source, edge.source_pad = instance.id, port_of[key]
    inner_edges = {e.id for e in inner.edges}
    outer.nodes = [n for n in outer.nodes if n.id not in selected] + [instance]
    outer.edges = [e for e in outer.edges if e.id not in inner_edges]
    moved_scripts, moved_probes = {s.id for s in inner.scripts}, {p.id for p in inner.probes}
    outer.scripts = [s for s in outer.scripts if s.id not in moved_scripts]
    outer.probes = [p for p in outer.probes if p.id not in moved_probes]
    component = Component(id=component_id, name=name or component_id, graph=inner, ports=ports)
    return component, outer


def expand_instance(graph: Graph, node_id: str, component: Component) -> Graph:
    """Replace an instance by a copy of the component's elements (an independent copy)."""
    instance = graph.node(node_id)
    if instance is None:
        raise GroupingError(f"node '{node_id}' does not exist")
    result = graph.model_copy(deep=True)
    result.nodes = [n for n in result.nodes if n.id != node_id]
    ids: dict[str, str] = {}
    for inner in component.graph.nodes:
        copy = inner.model_copy(deep=True)
        copy.id = new_node_id(result)
        copy.name = unique_name(result, f"{instance.name}_{inner.name}")
        copy.position = Position(
            x=instance.position.x + inner.position.x, y=instance.position.y + inner.position.y
        )
        ids[inner.id] = copy.id
        result.nodes.append(copy)
    _apply_parameters(result, component, instance, ids)
    for edge in component.graph.edges:
        copy = Edge(
            id=new_edge_id(result),
            source=ids[edge.source],
            source_pad=edge.source_pad,
            target=ids[edge.target],
            target_pad=edge.target_pad,
        )
        ids[edge.id] = copy.id
        result.edges.append(copy)
    ports = {p.name: p for p in component.ports}
    for edge in result.edges:
        if edge.source == node_id and edge.source_pad in ports:
            edge.source, edge.source_pad = ids[ports[edge.source_pad].node_id], ports[edge.source_pad].pad
        if edge.target == node_id and edge.target_pad in ports:
            edge.target, edge.target_pad = ids[ports[edge.target_pad].node_id], ports[edge.target_pad].pad
    for attached, collection in (
        (component.graph.scripts, result.scripts),
        (component.graph.probes, result.probes),
    ):
        for item in attached:
            if item.target.id in ids:  # inner node and edge ids were remapped above
                copy = item.model_copy(deep=True)
                copy.id, copy.target.id = f"{item.id}-{instance.name}", ids[item.target.id]
                collection.append(copy)
    return result


def _apply_parameters(graph: Graph, component: Component, instance: Node, ids: dict[str, str]) -> None:
    for param in component.parameters:
        value = instance.properties.get(param.name, param.default)
        if value is None:
            continue
        for target in param.targets:
            node = graph.node(ids.get(target.node_id, ""))
            if node is None:
                continue
            if target.pad:
                node.pad_properties.setdefault(target.pad, {})[target.property] = value
            else:
                node.properties[target.property] = value
