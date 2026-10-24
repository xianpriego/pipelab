"""Helpers to build suggestions whose fixes insert elements on a link."""

from __future__ import annotations

from pipelab.catalog.models import PropertyValue
from pipelab.graph.models import Edge, Fix, FixElement, PadRef, Suggestion


def chain_title(factories: list[str]) -> str:
    return "Insert " + " ! ".join(factories)


def insert_fix(edge: Edge, elements: list[FixElement], existing: bool) -> Fix:
    """Insert ``elements`` on ``edge`` (existing link) or between its pads (new link)."""
    if existing:
        return Fix(kind="insert_on_edge", edge_id=edge.id, elements=elements)
    return Fix(
        kind="connect_via",
        source=PadRef(node_id=edge.source, pad=edge.source_pad),
        target=PadRef(node_id=edge.target, pad=edge.target_pad),
        elements=elements,
    )


def insert_suggestion(
    edge: Edge,
    factories: list[str],
    existing: bool,
    description: str = "",
    properties: dict[str, dict[str, PropertyValue]] | None = None,
) -> Suggestion:
    props = properties or {}
    elements = [FixElement(factory=f, properties=props.get(f, {})) for f in factories]
    return Suggestion(
        title=chain_title(factories),
        description=description,
        fix=insert_fix(edge, elements, existing),
    )


def set_property_suggestion(node_id: str, name: str, value: PropertyValue, description: str) -> Suggestion:
    return Suggestion(
        title=f"Set {name}={value}",
        description=description,
        fix=Fix(kind="set_property", node_id=node_id, property=name, value=value),
    )
