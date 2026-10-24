"""Validation of a component definition: its graph, ports and parameters."""

from __future__ import annotations

from pipelab.components.models import Component
from pipelab.graph.analyzer import Analyzer
from pipelab.graph.models import Issue
from pipelab.graph.rules.base import issue
from pipelab.graph.rules.dynamic import IDENTIFIER
from pipelab.graph.validate import validate_graph

_PIPELINE_ONLY = {"no-source", "no-sink"}


def _is_port_issue(found: Issue, component: Component) -> bool:
    """Unlinked-pad issues for pads that are exposed as ports are expected."""
    if found.rule != "unlinked-pad":
        return False
    for port in component.ports:
        if found.id.endswith(f"{port.node_id}.{port.pad}"):
            return True
        if found.node_ids == [port.node_id] and found.id.endswith((".inputs", ".outputs")):
            return True
    return False


def _port_issues(analyzer: Analyzer, component: Component) -> list[Issue]:
    issues, names = [], set()
    for port in component.ports:
        node = component.graph.node(port.node_id)
        template = analyzer.catalog.pad_template(node.factory, port.pad) if node else None
        problem = None
        if port.name in names:
            problem = "the name is used twice"
        elif node is None:
            problem = "its element no longer exists"
        elif template is None or template.direction != port.direction:
            problem = f"'{node.name}' has no {port.direction} pad '{port.pad}'"
        elif (
            any(
                (e.source, e.source_pad) == (node.id, port.pad)
                or (e.target, e.target_pad) == (node.id, port.pad)
                for e in component.graph.edges
            )
            and template.presence == "always"
        ):
            problem = "the pad is already linked inside the component"
        names.add(port.name)
        if problem:
            issues.append(
                issue("component", "error", f"Port '{port.name}': {problem}.", key=f"port:{port.name}")
            )
    return issues


def _parameter_issues(analyzer: Analyzer, component: Component) -> list[Issue]:
    issues, names = [], set()
    for param in component.parameters:
        if not IDENTIFIER.match(param.name.replace("-", "_")) or param.name in names:
            issues.append(
                issue(
                    "component",
                    "error",
                    f"Parameter '{param.name}': invalid or duplicated name.",
                    key=f"param:{param.name}",
                )
            )
        names.add(param.name)
        for target in param.targets:
            node = component.graph.node(target.node_id)
            element = analyzer.catalog.get(node.factory) if node else None
            known = element is not None and (target.pad or element.property(target.property) is not None)
            if not known:
                issues.append(
                    issue(
                        "component",
                        "error",
                        f"Parameter '{param.name}': '{target.property}' is not a property of its target.",
                        key=f"param:{param.name}:{target.node_id}:{target.property}",
                    )
                )
    return issues


def validate_component(analyzer: Analyzer, component: Component) -> list[Issue]:
    issues = [
        found
        for found in validate_graph(analyzer, component.graph)
        if found.rule not in _PIPELINE_ONLY and not _is_port_issue(found, component)
    ]
    return issues + _port_issues(analyzer, component) + _parameter_issues(analyzer, component)
