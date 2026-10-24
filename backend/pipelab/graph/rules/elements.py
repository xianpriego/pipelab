"""Rules about the elements themselves: availability, names and properties."""

from __future__ import annotations

from collections import Counter

from pipelab.catalog.models import ElementInfo
from pipelab.components.models import component_id
from pipelab.graph.models import Issue, Node
from pipelab.graph.property_check import check_value
from pipelab.graph.rules.base import RuleContext, issue

REQUIRED_PROPERTY_NAMES = ("location", "uri")


def _missing_message(factory: str) -> str:
    component = component_id(factory)
    if component is not None:
        return f"Component '{component}' is not in the library."
    return f"Element '{factory}' is not installed in this GStreamer setup."


def missing_elements(ctx: RuleContext) -> list[Issue]:
    return [
        issue("missing-element", "error", _missing_message(node.factory), [node])
        for node in ctx.graph.nodes
        if ctx.element(node) is None
    ]


def duplicate_names(ctx: RuleContext) -> list[Issue]:
    counts = Counter(node.name for node in ctx.graph.nodes)
    return [
        issue(
            "duplicate-name",
            "error",
            f"Several elements are named '{name}'; element names must be unique.",
            [n for n in ctx.graph.nodes if n.name == name],
            key=name,
        )
        for name, count in counts.items()
        if count > 1
    ]


def _property_issues(node: Node, element: ElementInfo) -> list[Issue]:
    issues = []
    for name, value in node.properties.items():
        prop = element.property(name)
        if prop is None:
            issues.append(
                issue(
                    "invalid-property",
                    "error",
                    f"{node.name}: '{element.name}' has no property '{name}'.",
                    [node],
                    key=f"{node.id}.{name}",
                )
            )
        elif not prop.writable:
            issues.append(
                issue(
                    "invalid-property",
                    "error",
                    f"{node.name}: property '{name}' is read-only.",
                    [node],
                    key=f"{node.id}.{name}",
                )
            )
        elif (error := check_value(prop, value)) is not None:
            issues.append(
                issue("invalid-property", "error", f"{node.name}: {error}.", [node], key=f"{node.id}.{name}")
            )
    return issues


def _pad_property_issues(ctx: RuleContext, node: Node) -> list[Issue]:
    issues = []
    for pad, properties in node.pad_properties.items():
        template = ctx.analyzer.catalog.pad_template(node.factory, pad)
        known = {p.name: p for p in template.properties} if template else {}
        for name, value in properties.items():
            prop = known.get(name)
            error = f"pad '{pad}' has no property '{name}'" if prop is None else check_value(prop, value)
            if error:
                issues.append(
                    issue(
                        "invalid-property",
                        "error",
                        f"{node.name}: {error}.",
                        [node],
                        key=f"{node.id}.{pad}.{name}",
                    )
                )
    return issues


def properties(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, element in ctx.nodes_with(lambda _n, _e: True):
        issues += _property_issues(node, element)
        issues += _pad_property_issues(ctx, node)
    return issues


def required_properties(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, element in ctx.nodes_with(lambda _n, e: bool({"source", "sink"} & set(e.categories))):
        for name in REQUIRED_PROPERTY_NAMES:
            prop = element.property(name)
            if prop is None or prop.type != "string" or not prop.writable or prop.default:
                continue
            if not str(node.properties.get(name, "")).strip():
                issues.append(
                    issue(
                        "required-property",
                        "error",
                        f"{node.name}: set '{name}' — {element.name} cannot start without it.",
                        [node],
                        key=f"{node.id}.{name}",
                    )
                )
    return issues
