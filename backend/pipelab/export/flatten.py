"""Expands component instances (and initial slot instances) into plain elements.

Used by the exports that cannot express components (gst-launch, C): inner
elements are renamed ``<instance>_<name>``, parameters become properties and
links to ports are redirected to the inner pads.
"""

from __future__ import annotations

from collections.abc import Mapping

from pipelab.catalog.store import is_template_name
from pipelab.components.models import Component, component_id, used_components
from pipelab.graph.models import Edge, Graph, Node
from pipelab.graph.pads import next_request_pad


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
    """Plain graph equivalent to ``graph`` before any dynamic change."""
    flattener = _Flattener(components)
    flattener.add_scope(graph, "", {})
    used: dict[tuple[str, str], set[str]] = {}
    for slot in graph.slots:
        definition = components.get(slot.component)
        if definition is None:
            continue
        for position, initial in enumerate(slot.initial):
            ports = flattener.instance(definition, f"{initial.id}_", dict(initial.params))
            index = _slot_index(slot.item, initial.id, position)
            for link in slot.links:
                inner = ports.get(link.port)
                port = next((p for p in definition.ports if p.name == link.port), None)
                if inner is None or port is None:
                    continue
                pad = link.pad
                taken = used.setdefault((link.node_id, pad), _linked_pads(flattener.edges, link.node_id))
                if is_template_name(pad):
                    pad = next_request_pad(pad, taken)
                taken.add(pad)
                node = next(n for n in flattener.nodes if n.id == link.node_id)
                props = {
                    k: _slot_value(v, index, initial.id, initial.params)
                    for k, v in link.pad_properties.items()
                }
                if props:
                    node.pad_properties[pad] = {**node.pad_properties.get(pad, {}), **props}
                edge_id = f"{initial.id}_{link.port}"
                if port.direction == "src":
                    edge = Edge(
                        id=edge_id, source=inner[0], source_pad=inner[1], target=link.node_id, target_pad=pad
                    )
                else:
                    edge = Edge(
                        id=edge_id, source=link.node_id, source_pad=pad, target=inner[0], target_pad=inner[1]
                    )
                flattener.edges.append(edge)
    return Graph(nodes=flattener.nodes, edges=flattener.edges, scripts=graph.scripts)


def _linked_pads(edges: list[Edge], node_id: str) -> set[str]:
    """Pads of ``node_id`` already used by links (request pads must not be reused)."""
    return {e.target_pad for e in edges if e.target == node_id} | {
        e.source_pad for e in edges if e.source == node_id
    }


def _slot_index(item: str, instance_id: str, position: int) -> int:
    """``$index`` like the exported libraries: the numeric suffix of ``<item><n>`` ids."""
    suffix = instance_id[len(item) :] if instance_id.startswith(item) else ""
    return int(suffix) if suffix.isdigit() else position


def _slot_value(value, index: int, instance_id: str, params: dict):
    if isinstance(value, str) and value.startswith("$$"):
        return value[1:]
    if isinstance(value, str) and value.startswith("$"):
        return {"index": index, "id": instance_id}.get(value[1:], params.get(value[1:]))
    return value


def dynamic_notes(graph: Graph, components: Mapping[str, Component] | None = None) -> list[str]:
    """Plain-text notes about what a static export leaves out."""
    lines = []
    inner = [
        f"{p.name} ({definition.id})"
        for definition in used_components(graph, dict(components or {})).values()
        for p in definition.graph.probes
        if p.enabled
    ]
    if graph.slots:
        lines.append(
            "Slots (rendered with their initial instances): "
            + ", ".join(f"{s.name} ({s.component}, {len(s.initial)} initial)" for s in graph.slots)
        )
    if graph.functions:
        lines.append("Pipeline API functions: " + ", ".join(f.name for f in graph.functions))
    probes = [p for p in graph.probes if p.enabled]
    if probes:
        lines.append("Probe rule sets: " + ", ".join(p.name for p in probes))
    if inner:
        lines.append("Probe rule sets of components: " + ", ".join(inner))
    if lines:
        lines.insert(0, "Dynamic parts need the Python or Rust export:")
    return lines
