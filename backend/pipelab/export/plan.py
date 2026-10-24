"""Language-neutral plan of a pipeline library: the graph and the components it uses.

``build_program`` resolves everything the Rust and Python generators need so
they only decide syntax: identifiers, typed parameters, how every component
port maps to an inner pad and which links wait for *sometimes* pads.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Literal

from pipelab.catalog.store import Catalog
from pipelab.components.models import Component, ComponentParam, component_id
from pipelab.export.common import PipelineSpec, build_spec, camel_case, identifier
from pipelab.graph.models import Graph, Node

ParamKind = Literal["string", "int", "float", "bool"]
_KINDS: dict[str, ParamKind] = {
    "boolean": "bool",
    "int": "int",
    "uint": "int",
    "int64": "int",
    "uint64": "int",
    "float": "float",
    "double": "float",
}


@dataclass(frozen=True)
class ParamTargetPlan:
    element: str  # inner element (or nested instance) name
    property: str
    pad: str | None
    pad_ref: bool  # GstPad-typed property: the value is a pad name


@dataclass(frozen=True)
class ParamPlan:
    name: str
    ident: str
    kind: ParamKind
    default: str | int | float | bool | None
    targets: tuple[ParamTargetPlan, ...]
    description: str = ""


@dataclass(frozen=True)
class PortPlan:
    name: str
    direction: str
    element: str
    pad: str
    presence: str  # always | request | sometimes


@dataclass(frozen=True)
class InstancePlan:
    node: Node
    component: ComponentPlan
    values: dict[str, str | int | float | bool]


@dataclass
class ScopePlan:
    """A graph to build into a container (the pipeline or a component bin)."""

    spec: PipelineSpec
    instances: dict[str, InstancePlan]  # node id → instance
    dynamic_edges: set[str]  # edges whose source is a sometimes pad or port

    def is_instance(self, node_id: str) -> bool:
        return node_id in self.instances


@dataclass
class ComponentPlan:
    component: Component
    ident: str  # build_<ident>
    type_name: str  # <TypeName>Params
    params: list[ParamPlan] = field(default_factory=list)
    ports: list[PortPlan] = field(default_factory=list)
    scope: ScopePlan | None = None

    @property
    def sink_ports(self) -> list[PortPlan]:
        return [p for p in self.ports if p.direction == "sink"]


@dataclass
class ProgramPlan:
    name: str
    type_name: str
    root: ScopePlan
    components: list[ComponentPlan]  # dependencies first


class _Planner:
    def __init__(
        self, catalog: Catalog, components: Mapping[str, Component], reserved: frozenset[str]
    ) -> None:
        self.catalog = catalog
        self.library = components
        self.reserved = reserved
        self.plans: dict[str, ComponentPlan] = {}
        self.order: list[ComponentPlan] = []
        self._visiting: set[str] = set()

    def component(self, cid: str) -> ComponentPlan:
        if cid in self.plans:
            return self.plans[cid]
        if cid in self._visiting:
            raise ValueError(f"component '{cid}' contains itself")
        definition = self.library.get(cid)
        if definition is None:
            raise KeyError(f"component '{cid}' is not in the library")
        self._visiting.add(cid)
        plan = ComponentPlan(definition, identifier(cid, self.reserved), camel_case(cid))
        plan.scope = self.scope(definition.graph)
        plan.params = [self._param(definition, p) for p in definition.parameters]
        plan.ports = [
            self._port(definition.graph, p.name, p.direction, p.node_id, p.pad) for p in definition.ports
        ]
        self._visiting.discard(cid)
        self.plans[cid] = plan
        self.order.append(plan)
        return plan

    def scope(self, graph: Graph) -> ScopePlan:
        instances: dict[str, InstancePlan] = {}
        for node in graph.nodes:
            cid = component_id(node.factory)
            if cid is not None:
                instances[node.id] = InstancePlan(node, self.component(cid), dict(node.properties))
        spec = build_spec(graph, self.catalog, "scope", self.reserved)
        dynamic = {link.edge.id for link in spec.links if link.dynamic}
        for edge in graph.edges:
            if edge.source in instances:
                port = next(
                    (p for p in instances[edge.source].component.ports if p.name == edge.source_pad), None
                )
                if port is not None and port.presence == "sometimes":
                    dynamic.add(edge.id)
        return ScopePlan(spec, instances, dynamic)

    def _param(self, definition: Component, param: ComponentParam) -> ParamPlan:
        nodes = {n.id: n for n in definition.graph.nodes}
        targets, kind = [], None
        for target in param.targets:
            node = nodes.get(target.node_id)
            if node is None:
                continue
            info = self._property(node, target.property, target.pad)
            kind = kind or (_KINDS.get(info.type, "string") if info is not None else None)
            pad_ref = info is not None and info.type == "pad"
            targets.append(ParamTargetPlan(node.name, target.property, target.pad, pad_ref))
        default = param.default
        resolved: ParamKind = kind or _kind_of(default)
        ident = identifier(param.name, self.reserved)
        return ParamPlan(param.name, ident, resolved, default, tuple(targets), param.description)

    def _property(self, node: Node, name: str, pad: str | None):
        cid = component_id(node.factory)
        if cid is not None:
            nested = self.component(cid)
            param = next((p for p in nested.params if p.name == name), None)
            return _FakeInfo(param.kind) if param else None
        if pad is not None:
            template = self.catalog.pad_template(node.factory, pad)
            return next((p for p in template.properties if p.name == name), None) if template else None
        element = self.catalog.get(node.factory)
        return element.property(name) if element else None

    def _port(self, graph: Graph, name: str, direction: str, node_id: str, pad: str) -> PortPlan:
        node = graph.node(node_id)
        if node is None:
            raise KeyError(f"port '{name}' points at a missing element")
        presence = "always"
        cid = component_id(node.factory)
        if cid is not None:
            inner = next((p for p in self.component(cid).ports if p.name == pad), None)
            presence = "sometimes" if inner is not None and inner.presence == "sometimes" else "always"
        else:
            template = self.catalog.pad_template(node.factory, pad)
            if template is not None and template.presence != "always":
                presence = template.presence
        return PortPlan(name, direction, node.name, pad, presence)


@dataclass(frozen=True)
class _FakeInfo:
    kind: ParamKind

    @property
    def type(self) -> str:
        return {"bool": "boolean", "int": "int64", "float": "double", "string": "string"}[self.kind]


def _kind_of(value: object) -> ParamKind:
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    return "string"


def build_program(
    graph: Graph,
    catalog: Catalog,
    components: Mapping[str, Component],
    name: str,
    reserved: frozenset[str] = frozenset(),
) -> ProgramPlan:
    planner = _Planner(catalog, components, reserved)
    root = planner.scope(graph)
    return ProgramPlan(name, camel_case(name), root, planner.order)
