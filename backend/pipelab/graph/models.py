"""Pipeline graph and validation result models (the API contract)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from pipelab.catalog.models import PropertyValue

Severity = Literal["error", "warning", "info"]


class Position(BaseModel):
    x: float = 0.0
    y: float = 0.0


class Node(BaseModel):
    id: str
    factory: str
    name: str
    properties: dict[str, PropertyValue] = Field(default_factory=dict)
    pad_properties: dict[str, dict[str, PropertyValue]] = Field(default_factory=dict)
    position: Position = Field(default_factory=Position)
    preview: Literal["auto", "off"] = "auto"


class Edge(BaseModel):
    id: str
    source: str
    source_pad: str
    target: str
    target_pad: str


class Graph(BaseModel):
    # Unknown keys are ignored, so documents saved by older versions still load.
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)

    def node(self, node_id: str) -> Node | None:
        return next((n for n in self.nodes if n.id == node_id), None)

    def node_by_name(self, name: str) -> Node | None:
        return next((n for n in self.nodes if n.name == name), None)

    def edge(self, edge_id: str) -> Edge | None:
        return next((e for e in self.edges if e.id == edge_id), None)

    def incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]

    def outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]


class FixElement(BaseModel):
    factory: str
    properties: dict[str, PropertyValue] = Field(default_factory=dict)


class PadRef(BaseModel):
    node_id: str
    pad: str


FixKind = Literal["insert_on_edge", "connect_via", "set_property", "insert_tee", "insert_after"]


class Fix(BaseModel):
    """A machine-applicable change to a graph (see ``graph/fixes.py``)."""

    kind: FixKind
    edge_id: str | None = None
    edge_ids: list[str] = Field(default_factory=list)
    node_id: str | None = None
    source: PadRef | None = None
    target: PadRef | None = None
    elements: list[FixElement] = Field(default_factory=list)
    property: str | None = None
    value: PropertyValue | None = None


class Suggestion(BaseModel):
    title: str
    description: str = ""
    fix: Fix


class Issue(BaseModel):
    id: str
    rule: str
    severity: Severity
    message: str
    node_ids: list[str] = Field(default_factory=list)
    edge_ids: list[str] = Field(default_factory=list)
    suggestions: list[Suggestion] = Field(default_factory=list)


class LinkCheckResult(BaseModel):
    allowed: bool
    severity: Literal["ok", "info", "warning", "error"]
    edge: Edge
    source_caps: str = ""
    target_caps: str = ""
    common_caps: str | None = None
    issues: list[Issue] = Field(default_factory=list)
