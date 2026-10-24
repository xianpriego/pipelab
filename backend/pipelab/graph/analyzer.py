"""Shared, catalog-bound services used by link checks, rules and fixes."""

from __future__ import annotations

from pipelab.catalog.models import ElementInfo
from pipelab.catalog.store import Catalog
from pipelab.components.models import Component
from pipelab.graph.bridge import BridgeFinder
from pipelab.graph.caps_flow import CapsFlow
from pipelab.graph.models import Graph, Node


class Analyzer:
    """Holds the catalog (with library components), the components and the bridge finder."""

    def __init__(self, catalog: Catalog, components: dict[str, Component] | None = None) -> None:
        self.catalog = catalog
        self.components = components or {}
        self.bridges = BridgeFinder(catalog)

    def element(self, node: Node) -> ElementInfo | None:
        return self.catalog.get(node.factory)

    def flow(self, graph: Graph) -> CapsFlow:
        return CapsFlow(graph, self.catalog)
