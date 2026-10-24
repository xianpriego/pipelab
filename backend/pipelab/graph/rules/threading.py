"""Threading best practices: queues after tees and demuxers, before aggregators."""

from __future__ import annotations

from collections.abc import Callable

from pipelab.catalog.models import ElementInfo
from pipelab.graph.caps_flow import QUEUE_LIKE
from pipelab.graph.models import Edge, Fix, FixElement, Issue, Node, Suggestion
from pipelab.graph.rules.base import RuleContext, issue
from pipelab.gst.values import parse_bool

LIVE_SOURCES = {
    "v4l2src",
    "rtspsrc",
    "udpsrc",
    "srtsrc",
    "ristsrc",
    "rtmpsrc",
    "rtmp2src",
    "souphttpsrc",
    "ximagesrc",
    "pipewiresrc",
    "pulsesrc",
    "alsasrc",
    "autoaudiosrc",
    "autovideosrc",
    "ndisrc",
    "webrtcsrc",
    "whepsrc",
    "decklinkvideosrc",
    "decklinkaudiosrc",
    "libcamerasrc",
    "tcpclientsrc",
    "tcpserversrc",
    "nvarguscamerasrc",
}


def _queue_suggestion(edges: list[Edge]) -> Suggestion:
    plural = "s" if len(edges) > 1 else ""
    return Suggestion(
        title=f"Insert queue{plural}",
        description="Each queue starts a new streaming thread.",
        fix=Fix(
            kind="insert_on_edge", edge_ids=[e.id for e in edges], elements=[FixElement(factory="queue")]
        ),
    )


def _without_queue(ctx: RuleContext, edges: list[Edge], upstream: bool = False) -> list[Edge]:
    def peer(edge: Edge) -> Node:
        return ctx.source(edge) if upstream else ctx.target(edge)

    return [e for e in edges if peer(e).factory not in QUEUE_LIKE]


def _branches_without_queue(
    ctx: RuleContext, splitter: Callable[[Node, ElementInfo], bool], rule: str, advice: str
) -> list[Issue]:
    """Elements pushing several branches from one thread need a queue at the start of each."""
    issues = []
    for node, _element in ctx.nodes_with(splitter):
        outgoing = ctx.graph.outgoing(node.id)
        missing = _without_queue(ctx, outgoing)
        if len(outgoing) >= 2 and missing:
            issues.append(
                issue(
                    rule, "warning", f"{node.name}: {advice}", [node], missing, [_queue_suggestion(missing)]
                )
            )
    return issues


def tee_branches(ctx: RuleContext) -> list[Issue]:
    return _branches_without_queue(
        ctx,
        lambda node, _element: node.factory == "tee",
        "tee-queue",
        "start every tee branch with a queue. Without it all branches share one thread and a blocked "
        "branch (e.g. a sink prerolling) stalls the others.",
    )


def demuxer_branches(ctx: RuleContext) -> list[Issue]:
    return _branches_without_queue(
        ctx,
        lambda _node, element: "demuxer" in element.categories,
        "demuxer-queue",
        "put a queue on each demuxer output. Demuxers push all streams from one thread, so a branch "
        "waiting for data from another one deadlocks while prerolling.",
    )


def _is_aggregator(_node: Node, element: ElementInfo) -> bool:
    return element.is_a("GstAggregator") or bool({"muxer", "mixer"} & set(element.categories))


def aggregator_inputs(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, _element in ctx.nodes_with(_is_aggregator):
        incoming = ctx.graph.incoming(node.id)
        missing = _without_queue(ctx, incoming, upstream=True)
        if len(incoming) >= 2 and missing:
            issues.append(
                issue(
                    "aggregator-queue",
                    "info",
                    f"{node.name}: add a queue before each input so every stream is produced in its own "
                    "thread and the aggregator can wait for all of them without blocking.",
                    [node],
                    missing,
                    [_queue_suggestion(missing)],
                )
            )
    return issues


def _is_live(node: Node, element: ElementInfo) -> bool:
    if "source" not in element.categories:
        return False
    return node.factory in LIVE_SOURCES or parse_bool(node.properties.get("is-live"))


def live_sources(ctx: RuleContext) -> list[Issue]:
    issues = []
    for node, _element in ctx.nodes_with(_is_live):
        heavy = [
            e
            for e in ctx.graph.outgoing(node.id)
            if (target := ctx.analyzer.catalog.get(ctx.target(e).factory)) is not None
            and {"encoder", "muxer"} & set(target.categories)
        ]
        if heavy:
            issues.append(
                issue(
                    "live-source-queue",
                    "info",
                    f"{node.name} is a live source feeding a heavy element directly. A queue decouples "
                    "capture from encoding so slow frames do not make the source drop data.",
                    [node],
                    heavy,
                    [_queue_suggestion(heavy)],
                )
            )
    return issues
