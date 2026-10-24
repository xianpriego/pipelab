"""Components (macro blocks): reusable sub-graphs with ports and parameters."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from pipelab.graph.models import Graph
from pipelab.graph.probes import Value

COMPONENT_PREFIX = "component:"


class ComponentPort(BaseModel):
    """An inner pad exposed on the component (a ghost pad of its GstBin)."""

    name: str
    direction: Literal["src", "sink"]
    node_id: str
    pad: str  # inner pad name or template (request/sometimes)


class ParamTarget(BaseModel):
    node_id: str
    property: str
    pad: str | None = None  # set a pad property instead (request pads)


class ComponentParam(BaseModel):
    name: str  # identifier used as the instance property name and in code
    description: str = ""
    default: Value = None  # None: the inner property's own value
    targets: list[ParamTarget] = Field(default_factory=list)


class Component(BaseModel):
    id: str  # slug, e.g. "rtsp-input"; instances use factory "component:<id>"
    name: str
    description: str = ""
    version: int = 1
    updated_at: datetime | None = None
    graph: Graph = Field(default_factory=Graph)
    ports: list[ComponentPort] = Field(default_factory=list)
    parameters: list[ComponentParam] = Field(default_factory=list)

    @property
    def factory(self) -> str:
        return f"{COMPONENT_PREFIX}{self.id}"


def component_id(factory: str) -> str | None:
    return factory[len(COMPONENT_PREFIX) :] if factory.startswith(COMPONENT_PREFIX) else None


def used_components(graph: Graph, library: dict[str, Component]) -> dict[str, Component]:
    """Definitions a graph needs (instances, slots and nested components)."""
    needed: dict[str, Component] = {}
    pending = [component_id(node.factory) for node in graph.nodes] + [slot.component for slot in graph.slots]
    while pending:
        current = pending.pop()
        if current is None or current in needed or current not in library:
            continue
        needed[current] = library[current]
        pending += [component_id(node.factory) for node in library[current].graph.nodes]
    return needed


def references(graph: Graph, component: str) -> bool:
    """Whether a graph uses a component directly (an instance node or a slot)."""
    return any(component_id(node.factory) == component for node in graph.nodes) or any(
        slot.component == component for slot in graph.slots
    )
