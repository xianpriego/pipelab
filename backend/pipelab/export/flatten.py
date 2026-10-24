"""Expands component instances into plain elements.

Used by the exports that cannot express components (gst-launch, C): inner
elements are renamed ``<instance>_<name>``, parameters become properties and
links to ports are redirected to the inner pads.
"""

from __future__ import annotations

from collections.abc import Mapping

from pipelab.components.models import Component, component_id
from pipelab.graph.models import Edge, Graph, Node


class _Flattener:
    def __init__(self, components: Mapping[str, Component]) -> None:
        self.components = components
        self.nodes: list[Node] = []
        self.edges: list[Edge] = []

    def add_scope(self, graph: Graph, prefix: str, overrides: dict[str, dict]) -> dict[str, tuple[str, str]]:
        """Copy a graph; returns port → (flat node id, pad) for instance ports (keyed "<node id>.<port>")."""
        ports: dict[str, tuple[str, str]] = {}
        for node in graph.nodes:
            cid = component_id(node.factory)
            definition = self.components.get(cid) if cid else None
            flat_id, flat_name = f"{prefix}{node.id}", f"{prefix}{node.name}"
            if definition is None:
                properties = {**node.properties, **overrides.get(node.id, {}).get("properties", {})}
                pads = {**node.pad_properties}
                for pad, values in overrides.get(node.id, {}).get("pads", {}).items():
                    pads[pad] = {**pads.get(pad, {}), **values}
                self.nodes.append(
                    node.model_copy(
                        update={
                            "id": flat_id,
                            "name": flat_name,
                            "properties": properties,
                            "pad_properties": pads,
                        }
                    )
                )
                continue
            values = {**node.properties, **overrides.get(node.id, {}).get("properties", {})}
            inner = self.instance(definition, f"{flat_name}_", values)
            for port, target in inner.items():
                ports[f"{node.id}.{port}"] = target
        for edge in graph.edges:
            source = ports.get(
                f"{edge.source}.{edge.source_pad}", (f"{prefix}{edge.source}", edge.source_pad)
            )
            target = ports.get(
                f"{edge.target}.{edge.target_pad}", (f"{prefix}{edge.target}", edge.target_pad)
            )
            self.edges.append(
                Edge(
                    id=f"{prefix}{edge.id}",
                    source=source[0],
                    source_pad=source[1],
                    target=target[0],
                    target_pad=target[1],
                )
            )
        return ports

    def instance(self, definition: Component, prefix: str, values: dict) -> dict[str, tuple[str, str]]:
        overrides: dict[str, dict] = {}
        for param in definition.parameters:
            value = values.get(param.name, param.default)
            if value is None:
                continue
            for target in param.targets:
                entry = overrides.setdefault(target.node_id, {"properties": {}, "pads": {}})
                if target.pad:
                    entry["pads"].setdefault(target.pad, {})[target.property] = value
                else:
                    entry["properties"][target.property] = value
        inner_ports = self.add_scope(definition.graph, prefix, overrides)
        result = {}
        for port in definition.ports:
            result[port.name] = inner_ports.get(
                f"{port.node_id}.{port.pad}", (f"{prefix}{port.node_id}", port.pad)
            )
        return result


def flatten(graph: Graph, components: Mapping[str, Component]) -> Graph:
    """Plain graph equivalent to ``graph``: every component instance replaced by its elements."""
    flattener = _Flattener(components)
    flattener.add_scope(graph, "", {})
    return Graph(nodes=flattener.nodes, edges=flattener.edges)
