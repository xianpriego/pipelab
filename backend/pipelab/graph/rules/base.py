"""Shared context and helpers for graph validation rules."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from pipelab.catalog.models import ElementInfo
from pipelab.graph.analyzer import Analyzer
from pipelab.graph.caps_flow import CapsFlow
from pipelab.graph.models import Edge, Graph, Issue, Node, Severity, Suggestion


@dataclass
class RuleContext:
    graph: Graph
    analyzer: Analyzer
    flow: CapsFlow = field(init=False)

    def __post_init__(self) -> None:
        self.flow = self.analyzer.flow(self.graph)

    def element(self, node: Node) -> ElementInfo | None:
        return self.analyzer.catalog.get(node.factory)

    def nodes_with(self, predicate: Callable[[Node, ElementInfo], bool]) -> list[tuple[Node, ElementInfo]]:
        result = []
        for node in self.graph.nodes:
            element = self.element(node)
            if element is not None and predicate(node, element):
                result.append((node, element))
        return result

    def target(self, edge: Edge) -> Node:
        node = self.graph.node(edge.target)
        assert node is not None
        return node

    def source(self, edge: Edge) -> Node:
        node = self.graph.node(edge.source)
        assert node is not None
        return node


def issue(
    rule: str,
    severity: Severity,
    message: str,
    nodes: list[Node] | None = None,
    edges: list[Edge] | None = None,
    suggestions: list[Suggestion] | None = None,
    key: str = "",
) -> Issue:
    node_ids = [n.id for n in nodes or []]
    edge_ids = [e.id for e in edges or []]
    subject = key or ",".join(node_ids + edge_ids)
    return Issue(
        id=f"{rule}:{subject}",
        rule=rule,
        severity=severity,
        message=message,
        node_ids=node_ids,
        edge_ids=edge_ids,
        suggestions=suggestions or [],
    )


Rule = Callable[[RuleContext], list[Issue]]
