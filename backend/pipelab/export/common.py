"""Language-neutral view of a graph shared by every code generator.

``build_spec`` resolves, once, everything generators need: element order,
identifiers, how each property must be set (typed setter, string parsing or
pad lookup) and which links are static or wait for a *sometimes* pad.
"""

from __future__ import annotations

import keyword
import re
from dataclasses import dataclass
from typing import Literal

from pipelab.catalog.models import PropertyInfo, PropertyValue
from pipelab.catalog.store import Catalog, is_template_name
from pipelab.graph.models import Edge, Graph, Node
from pipelab.graph.pads import next_request_pad
from pipelab.graph.topology import topological_order
from pipelab.gst.values import to_launch_string

PropertyKind = Literal["bool", "int", "uint", "int64", "uint64", "float", "double", "string", "parse", "pad"]
_NUMERIC_KINDS = {"int", "uint", "int64", "uint64"}
_FLOAT_KINDS = {"float", "double"}
_TYPED_KINDS = {"boolean": "bool", "string": "string", "pad": "pad"}


@dataclass(frozen=True)
class PropertySpec:
    name: str
    value: PropertyValue
    kind: PropertyKind

    @property
    def text(self) -> str:
        """Value as ``gst-launch``/``gst_util_set_object_arg`` would parse it."""
        return to_launch_string(self.value)


@dataclass(frozen=True)
class ElementSpec:
    node: Node
    ident: str
    properties: tuple[PropertySpec, ...]
    pad_refs: tuple[PropertySpec, ...]
    pad_properties: tuple[tuple[str, tuple[PropertySpec, ...]], ...]

    @property
    def name(self) -> str:
        return self.node.name

    @property
    def factory(self) -> str:
        return self.node.factory

    @property
    def typed_properties(self) -> tuple[PropertySpec, ...]:
        return tuple(p for p in self.properties if p.kind != "parse")

    @property
    def parsed_properties(self) -> tuple[PropertySpec, ...]:
        return tuple(p for p in self.properties if p.kind == "parse")


@dataclass(frozen=True)
class LinkSpec:
    edge: Edge
    source: ElementSpec
    target: ElementSpec
    source_pad: str
    target_pad: str
    dynamic: bool


@dataclass(frozen=True)
class PipelineSpec:
    name: str
    elements: tuple[ElementSpec, ...]
    links: tuple[LinkSpec, ...]

    @property
    def static_links(self) -> tuple[LinkSpec, ...]:
        return tuple(link for link in self.links if not link.dynamic)

    @property
    def dynamic_links(self) -> tuple[LinkSpec, ...]:
        return tuple(link for link in self.links if link.dynamic)


def identifier(name: str, reserved: frozenset[str] = frozenset()) -> str:
    """Valid snake_case identifier for ``name`` (``video-src.1`` → ``video_src_1``)."""
    ident = re.sub(r"\W+", "_", name).strip("_").lower() or "element"
    if ident[0].isdigit():
        ident = f"e_{ident}"
    if keyword.iskeyword(ident) or ident in reserved:
        ident = f"{ident}_"
    return ident


def camel_case(name: str) -> str:
    words = re.split(r"[^0-9A-Za-z]+", name)
    camel = "".join(word[:1].upper() + word[1:] for word in words if word)
    if not camel or camel[0].isdigit():
        camel = f"P{camel}"
    return camel


def slug(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "_", name).strip("_").lower() or "pipeline"


def property_kind(info: PropertyInfo | None, value: PropertyValue) -> PropertyKind:
    """How a value must be applied: typed setter, pad lookup or string parsing."""
    if info is None:
        return "parse"
    if info.type in _TYPED_KINDS:
        kind = _TYPED_KINDS[info.type]
        return kind if kind != "bool" or isinstance(value, bool) else "parse"
    is_number = isinstance(value, int | float) and not isinstance(value, bool)
    if info.type in _NUMERIC_KINDS and is_number and float(value).is_integer():
        return info.type  # type: ignore[return-value]
    if info.type in _FLOAT_KINDS and is_number:
        return info.type  # type: ignore[return-value]
    return "parse"


def _property_specs(values: dict[str, PropertyValue], infos: list[PropertyInfo]) -> tuple[PropertySpec, ...]:
    by_name = {info.name: info for info in infos}
    return tuple(
        PropertySpec(name, value, property_kind(by_name.get(name), value))
        for name, value in sorted(values.items())
        if name != "name"
    )


def _element_spec(node: Node, catalog: Catalog, ident: str) -> ElementSpec:
    element = catalog.get(node.factory)
    specs = _property_specs(node.properties, element.properties if element else [])
    pad_properties = []
    for pad, values in sorted(node.pad_properties.items()):
        template = catalog.pad_template(node.factory, pad)
        pad_properties.append((pad, _property_specs(values, template.properties if template else [])))
    return ElementSpec(
        node=node,
        ident=ident,
        properties=tuple(p for p in specs if p.kind != "pad"),
        pad_refs=tuple(p for p in specs if p.kind == "pad"),
        pad_properties=tuple(pad_properties),
    )


def _concrete(catalog: Catalog, node: Node, pad: str, used: set[str]) -> str:
    """Request template names left in a graph (``sink_%u``) get a free concrete name."""
    template = catalog.pad_template(node.factory, pad)
    if template is not None and template.presence == "request" and is_template_name(pad):
        pad = next_request_pad(pad, used)
        used.add(pad)
    return pad


def build_spec(
    graph: Graph, catalog: Catalog, name: str, reserved: frozenset[str] = frozenset()
) -> PipelineSpec:
    order = topological_order(graph)
    rank = {node_id: index for index, node_id in enumerate(order)}
    nodes = {node.id: node for node in graph.nodes}
    elements: dict[str, ElementSpec] = {}
    taken: set[str] = set()
    for node_id in order:
        ident = identifier(nodes[node_id].name, reserved)
        while ident in taken:
            ident = f"{ident}_{len(taken)}"
        taken.add(ident)
        elements[node_id] = _element_spec(nodes[node_id], catalog, ident)
    edges = [e for e in graph.edges if e.source in nodes and e.target in nodes]
    used: dict[tuple[str, str], set[str]] = {}
    for edge in edges:
        for key, pad in (((edge.source, "src"), edge.source_pad), ((edge.target, "sink"), edge.target_pad)):
            if not is_template_name(pad):
                used.setdefault(key, set()).add(pad)
    links = []
    for edge in sorted(edges, key=lambda e: (rank[e.source], rank[e.target], e.source_pad, e.id)):
        source, target = nodes[edge.source], nodes[edge.target]
        template = catalog.pad_template(source.factory, edge.source_pad)
        dynamic = template is not None and template.presence == "sometimes"
        source_pad = edge.source_pad
        if not dynamic:
            source_pad = _concrete(catalog, source, source_pad, used.setdefault((source.id, "src"), set()))
        target_pad = _concrete(catalog, target, edge.target_pad, used.setdefault((target.id, "sink"), set()))
        links.append(
            LinkSpec(edge, elements[source.id], elements[target.id], source_pad, target_pad, dynamic)
        )
    return PipelineSpec(name=name, elements=tuple(elements[i] for i in order), links=tuple(links))
