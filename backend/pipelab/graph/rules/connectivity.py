"""Rules about how elements are wired: links, unlinked pads, sources and sinks."""

from __future__ import annotations

from pipelab.catalog.models import ElementInfo
from pipelab.graph.link_check import check_link
from pipelab.graph.models import Issue, Node
from pipelab.graph.rules.base import RuleContext, issue


def links(ctx: RuleContext) -> list[Issue]:
    """Every existing edge must pass the same checks as a new connection."""
    issues: list[Issue] = []
    for edge in ctx.graph.edges:
        issues += check_link(ctx.analyzer, ctx.graph, edge).issues
    return issues


def _unlinked(node: Node, element: ElementInfo, ctx: RuleContext) -> list[Issue]:
    sinks = {e.target_pad for e in ctx.graph.incoming(node.id)}
    srcs = {e.source_pad for e in ctx.graph.outgoing(node.id)}
    issues = []
    for template in element.pad_templates:
        if template.presence != "always":
            continue
        if template.direction == "sink" and template.name not in sinks:
            issues.append(
                issue(
                    "unlinked-pad",
                    "error",
                    f"{node.name}: input pad '{template.name}' is not linked; it will never get data.",
                    [node],
                    key=f"{node.id}.{template.name}",
                )
            )
        if template.direction == "src" and template.name not in srcs:
            issues.append(
                issue(
                    "unlinked-pad",
                    "error",
                    f"{node.name}: output pad '{template.name}' is not linked; the pipeline would fail "
                    "with a 'not-linked' error.",
                    [node],
                    key=f"{node.id}.{template.name}",
                )
            )
    issues += _dynamic_unlinked(node, element, sinks, srcs)
    return issues


def _dynamic_unlinked(node: Node, element: ElementInfo, sinks: set[str], srcs: set[str]) -> list[Issue]:
    presences = {(t.direction, t.presence) for t in element.pad_templates}
    has_always = {d for d, p in presences if p == "always"}
    if ("sink", "request") in presences and "sink" not in has_always and not sinks:
        return [
            issue(
                "unlinked-pad",
                "error",
                f"{node.name} needs at least one input.",
                [node],
                key=f"{node.id}.inputs",
            )
        ]
    if "src" not in has_always and not srcs and ({("src", "sometimes"), ("src", "request")} & presences):
        severity = "error" if ("src", "sometimes") in presences else "warning"
        return [
            issue(
                "unlinked-pad",
                severity,
                f"{node.name} has no outputs linked; its data has nowhere to go.",
                [node],
                key=f"{node.id}.outputs",
            )
        ]
    return []


def unlinked_pads(ctx: RuleContext) -> list[Issue]:
    issues: list[Issue] = []
    for node, element in ctx.known_nodes():
        issues += _unlinked(node, element, ctx)
    return issues


def endpoints(ctx: RuleContext) -> list[Issue]:
    """A runnable pipeline needs at least one source and one sink."""
    known = ctx.known_nodes()
    if not known:
        return []
    directions = [{t.direction for t in element.pad_templates} for _node, element in known]
    issues = []
    if not any(d == {"src"} for d in directions):
        issues.append(
            issue(
                "no-source",
                "error",
                "The pipeline has no source element (e.g. videotestsrc, filesrc, v4l2src).",
                key="graph",
            )
        )
    if not any(d == {"sink"} for d in directions):
        issues.append(
            issue(
                "no-sink",
                "error",
                "The pipeline has no sink element (e.g. autovideosink, filesink, fakesink).",
                key="graph",
            )
        )
    return issues
